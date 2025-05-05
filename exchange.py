class Node:
    __slots__ = ("value", "prev", "next")          # keeps the nodes leaner
    def __init__(self, value, prev=None, nxt=None):
        self.value = value
        self.prev  = prev
        self.next  = nxt

class LinkedList:
    def __init__(self):
        # two sentinels make the edge‑case code vanish
        self.head = Node(None)                     # dummy head
        self.tail = Node(None)                     # dummy tail
        self.head.next = self.tail
        self.tail.prev = self.head
        self._size = 0

    # ---------- O(1) primitives ----------
    def insert_after(self, node, value):
        """Insert new node after *node* (node can be head sentinel)."""
        new = Node(value, prev=node, nxt=node.next)
        node.next.prev = new
        node.next = new
        self._size += 1
        return new                                 # hand back the 'pointer'

    def remove(self, node):
        """Unlink *node* in O(1).  Undefined behaviour for sentinels."""
        node.prev.next = node.next
        node.next.prev = node.prev
        node.prev = node.next = None               # help GC / catch bugs
        self._size -= 1
        return node.value

    # ---------- convenience wrappers ----------
    def push_front(self, value):
        return self.insert_after(self.head, value)

    def push_back(self, value):
        return self.insert_after(self.tail.prev, value)

    def pop_front(self):
        if self._size == 0:
            raise IndexError("pop from empty list")
        return self.remove(self.head.next)

    def pop_back(self):
        if self._size == 0:
            raise IndexError("pop from empty list")
        return self.remove(self.tail.prev)

    def __len__(self):
        return self._size

    def __iter__(self):                            # O(n) traversal
        cur = self.head.next
        while cur is not self.tail:
            yield cur.value
            cur = cur.next


from typing import Dict, List, Tuple, Union
import requests
from blockchain_client import PosNodeClient
client = PosNodeClient()
wallet_addr="fae5af82-3a13-4a83-81d1-247408f3f45e"

# r = client.create_transaction(wallet_addr, "HI", 1300)
# print(r)     # 201 → {"message": "... Block #N"}
from sortedcontainers import SortedDict
import uuid


class Order:
    def __init__(self, addr: str, size: int, price: int, buy: bool = True):
        self.id = str(uuid.uuid4())
        self.buy = buy
        self.addr = addr
        self.size = size
        self.price = price
        if self.buy:
            self.remaining = price * self.size
        else:
            self.remaining = self.size
        
class Market:
    def __init__(self, host: str = "127.0.0.1", port: Union[int, str] = 10000):
        # price → FIFO queue of orders
        # For bids we store *negative* price so the best bid appears first when peeking index‑0
        self.bids: SortedDict[int, LinkedList] = SortedDict()
        self.asks: SortedDict[int, LinkedList] = SortedDict()
        self.addr = "MARKET_ADDR"

        # order_id → (price_key, *_Node_*) so we can cancel in O(1)
        self.open_orders: Dict[str, (int, Node)] = {}
        self.client = PosNodeClient(host, port)
        self.client.create_transaction("0", self.addr, 10000000000)
        self.client.create_transaction("0", self.addr, 10000000000, token="SECOND")

    # --------------------------------------------------------
    # order entry / cancel
    # --------------------------------------------------------
    def add_order(self, order: Order):
        """Add an order and store its node pointer for O(1) cancel."""
        if order.buy:
            try:
                r = self.client.create_transaction(order.addr, self.addr, order.remaining)
            except: 
                return None
        else:
            try:
                r = self.client.create_transaction(order.addr, self.addr, order.remaining, token="SECOND")
            except:
                return None
        if order.buy:
            key = -order.price           # negate so high price == low key
            book = self.bids
        else:
            key = order.price
            book = self.asks

        if key not in book:
            book[key] = LinkedList()
        node = book[key].push_back(order)

        # (price_key, node, side_is_bid)
        self.open_orders[order.id] = (key, node)
        self.resolve_market(order.buy)
        return order.id

    def cancel(self, order_id: str) -> bool:
        rec = self.open_orders.pop(order_id, None)
        if rec is None:
            return False
        key, node = rec
        book = self.bids if node.value.buy else self.asks
        order = node.value
        ll = book[key]
        ll.remove(node)
        if order.buy:
            r = self.client.create_transaction(self.addr, order.addr, order.remaining)
        else:
            r = self.client.create_transaction(self.addr, order.addr, order.remaining, token="SECOND")
        if len(ll) == 0:
            del book[key]
        return True

    # --------------------------------------------------------
    # Matching loop
    # --------------------------------------------------------
    def resolve_market(self, buy: bool) -> List[Tuple[str, str, int, int]]:
        """Run continuous matching until best bid < best ask.

        Returns a list of trades as tuples: (bid_id, ask_id, size, price)"""
        trades: List[Tuple[str, str, int, int]] = []

        while self.bids and self.asks:
            best_bid_key, bid_queue = self.bids.peekitem(0)     # smallest *negative* key
            best_ask_key, ask_queue = self.asks.peekitem(0)     # smallest positive key

            best_bid_price = -best_bid_key
            best_ask_price = best_ask_key

            if best_bid_price < best_ask_price:
                break   # market crossed, nothing to do

            bid_node = bid_queue.head.next
            ask_node = ask_queue.head.next
            bid_order: Order = bid_node.value
            ask_order: Order = ask_node.value

            trade_qty = min(bid_order.size, ask_order.size)
            if buy:
                trade_price = ask_order.price   # classic price‑time: use resting price (ask)
            else:
                trade_price = bid_order.price
            trades.append((bid_order.id, ask_order.id, trade_qty, trade_price))

            # decrement sizes & clean up if filled
            bid_order.size -= trade_qty
            bid_order.remaining -= trade_qty * trade_price
            ask_order.size -= trade_qty
            ask_order.remaining -= trade_qty
            
            self.client.create_transaction(self.addr, bid_order.addr, trade_qty, token="SECOND")
            self.client.create_transaction(self.addr, ask_order.addr, trade_qty * trade_price)

            if bid_order.size == 0:
                self.client.create_transaction(self.addr, bid_order.addr, bid_order.remaining)
                bid_queue.remove(bid_node)
                self.open_orders.pop(bid_order.id, None)
                if len(bid_queue) == 0:
                    del self.bids[best_bid_key]

            if ask_order.size == 0:
                ask_queue.remove(ask_node)
                self.open_orders.pop(ask_order.id, None)
                if len(ask_queue) == 0:
                    del self.asks[best_ask_key]

        return trades

    # --------------------------------------------------------
    # Convenience inspectors
    # --------------------------------------------------------
    def best_bid(self):
        if not self.bids:
            return None
        price = -self.bids.peekitem(0)[0]
        size = sum(o.size for o in self.bids.peekitem(0)[1])
        return price, size

    def best_ask(self):
        if not self.asks:
            return None
        price = self.asks.peekitem(0)[0]
        size = sum(o.size for o in self.asks.peekitem(0)[1])
        return price, size

if __name__ == "__main__":
    m = Market()

    # Place some orders
    id1 = m.add_order(Order(addr=wallet_addr, price=100, size=5, buy=True))            # bid 5@100
    id2 = m.add_order(Order(addr=wallet_addr, price=101, size=7, buy=True))            # bid 7@101  (better)

    id3 = m.add_order(Order(addr=wallet_addr, price=102, size=4, buy=False))           # ask 4@102 

    print("Trades:", m.resolve_market(True))
    print("Best bid/ask:", m.best_bid(), m.best_ask())
    print(id1)
    print(m.cancel(id1))
    print(m.cancel(id2))
    print(m.cancel(id3))
    
    print("Trades:", m.resolve_market(True))
    print("Best bid/ask:", m.best_bid(), m.best_ask())