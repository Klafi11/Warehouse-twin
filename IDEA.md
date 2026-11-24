# Warehouse in Motion

> An interactive e-commerce digital twin for a real-time Confluent Streamhouse demo

_CONCEPT BRIEF \| Python 3.12+ \| Simulation first, streaming second_

## The idea

Build a visually engaging, grid-based e-commerce fulfillment warehouse that behaves like a small, living operation. Customers place orders containing one to four products. Autonomous robots navigate aisles, collect goods from storage shelves, and deliver them to a packing station. Behind the scenes, shelf inventory is replenished from a back room through an inbound dock; supplier purchase orders replenish the back room. Batteries, charging queues, congestion, breakdowns, repairs, and stockouts create realistic operational trade-offs.

The warehouse is both a standalone interactive digital twin and, in later phases, a real-time event producer for Confluent Cloud. During a tech talk, the audience should see an operational event happen on the warehouse floor, then see its impact propagate through streams, transformations, analytics, and dashboards.

## What the audience experiences

- Watch robots move through a 2D warehouse map with aisles, shelves, inbound dock, back room, chargers, repair bay, and packing station.

- Submit orders live and see their lifecycle: created → allocated → picking → packed → completed (or delayed).

- Trigger controlled stress scenarios: order surge, robot failure, low inventory, charging bottleneck, blocked aisle, or delayed supplier delivery.

- Observe cause and effect: queue lengths, order latency, robot utilization, battery levels, stockouts, and throughput change in real time.

- Later, compare the same events in Confluent Cloud and a dashboard to show how streaming data becomes operational insight.

## Core simulation model

---

Domain Behavior to model

---

Warehouse map Configurable grid, walkable lanes, obstacles, shelf slots, stations, and narrow passages.

Orders & products 1--4 products per order; product catalog, stock allocation, order priorities, packing completion.

Robots Task assignment, pathfinding, collision avoidance, load capacity, pickup/drop-off time, battery drain and charging.

Inventory Shelf thresholds, back-room stock, replenishment jobs via inbound dock, supplier lead times and purchase orders.

Reliability Probabilistic failures, robot downtime, repair-crew dispatch, repair duration and return to service.

Simulation control Pause/resume, speed multiplier, deterministic random seed, reset, scenario presets, manual event injection.
---------------------------------------------------------------------------------------------------------------------------------------------------------

## Architecture and boundaries

Phase 1 is intentionally independent of Confluent: a Python simulation engine owns the authoritative state and advances it on a simulation clock. A web API accepts commands (submit order, inject failure, change demand) and streams state updates to the browser, for example over WebSockets. The frontend renders the map and provides scenario controls and basic KPIs. An event publisher interface records immutable domain events without coupling simulation rules to a specific broker.

Later, a Confluent adapter publishes those events to Confluent Cloud topics. Stream processing derives metrics and enriched views; a dashboard displays live operational health. OpenTofu provisions and tears down the cloud-side infrastructure reproducibly, with credentials handled through secrets/environment variables rather than source control.

## Illustrative event contracts

Events should carry event_id, event_type, schema_version, event_time, simulation_time, run_id, entity_id, and payload. Possible candidate event types: order_created, order_allocated, pick_started, item_picked, order_packed, robot_position_updated, robot_failed, robot_repaired, robot_charging_started, shelf_stock_low, replenishment_started, replenishment_completed, purchase_order_placed, supplier_delivery_received. Separate high-frequency telemetry from business events so the demo remains affordable and understandable.

## Delivery roadmap

### 01 --- Standalone digital twin

Implement grid, robots, orders, stock, replenishment, failures, charging, deterministic simulation, and an interactive live frontend. Demonstrate without cloud dependencies.

### 02 --- Event-ready twin

Introduce versioned event schemas, event log, replay, publisher abstraction, test scenarios, and observable simulation metrics.

### 03 --- Confluent integration

Provision Confluent Cloud resources with OpenTofu; stream events; apply transformations and aggregations; document setup and teardown.

### 04 --- Streamhouse story

Build live dashboards, stress-test scenarios, and a narrated end-to-end demo linking physical behavior to streaming insights.

## MVP success criteria

A presenter can start the warehouse locally with one command, see multiple robots safely complete multi-item orders, trigger a failure and an order surge, observe recovery and replenishment, and inspect a consistent event log. The simulation can be reset and replayed using a fixed seed. No Confluent account is required for this milestone.

## Grill-me questions: decisions to pressure-test

- Do robots pick individual items, move entire shelf pods, or carry totes? This choice changes the whole simulation.

- What is the smallest believable warehouse: grid size, SKU count, shelf count, robot count, and station count?

- How realistic must traffic coordination be: simple reservation-based movement or full multi-agent path planning?

- Should simulated time be accelerated, and which events must align to wall-clock time for the live demo?

- What does a robot failure do to its load and the lane it occupies? Who can recover blocked work?

- What happens when shelf stock, back-room stock, or supplier stock is insufficient?

- Which three KPIs best tell the story, and which stress scenario produces a clear before/after moment?

- What event volume is useful for the demo without flooding Confluent with position updates?

- What is the budget ceiling and acceptable cloud teardown time for repeated talks?

- How will you guarantee the demo is repeatable even if a network or cloud service fails?

Recommended starting point: settle the picking model and MVP scale, then build the deterministic simulation core and frontend before introducing cloud infrastructure.
