# Technical Specification: Add to Cart and Final Order Placed

This specification details the implementation of the concurrent-safe **Add to Cart** flow and the atomic **PlaceOrder API** for the AI-Driven NLP-Based Local Marketplace. It outlines the architectural patterns required to safely process simultaneous checkouts for identical products while preventing race conditions and maintaining strict database integrity.

---

## Goal
The goal of this module is to provide customers with a reliable checkout experience through the chatbot interface. It guarantees that when two or more users simultaneously attempt to purchase the same product with limited inventory, the system accurately decrements stock, prevents overselling, saves transaction records, and returns a unique `#orderID`.

---

## Constraints
* **Race Condition Mitigation:** The system must use database row-level locking (`SELECT FOR UPDATE` or equivalent pessimistic concurrency controls) to safely handle simultaneous actions on the same product record.
* **Hyperlocal Stock Validation:** Orders must be validated against real-time vendor database inventories before confirmation.
* **Atomic Transactions:** Stock decrementing, order creation, and cart state mutation must run inside an isolated database transaction block. Any failure must trigger a complete rollback.
* **Idempotency:** The payment and placement pipeline must be idempotent to prevent duplicate order generation from network re-tries.

---

## Project Layout
The new files and alterations integrate into the existing ecosystem as shown below:

```text
├── src/
│   ├── apps/
│   │   └── orders/
│   │       ├── __init__.py
│   │       ├── controllers.py      # Handles HTTP request/response for Cart & Orders
│   │       ├── services.py         # Contains core business logic (Atomic order placement, Stock check)
│   │       └── exceptions.py       # Custom exceptions (e.g., OutOfStockException)
│   ├── core/
│   │   └── database/
│   │       └── mixins.py           # Atomic locks and query helpers
│   ├── models/
│   │   └── order.py                # Database models for Order, OrderItem, and Cart
│   └── tests/
│       └── test_orders_concurrency.py # Concurrent load tests for simultaneous purchases