# Shipping Integration Requirements Specification

## 1. Introduction
We are an e-commerce bookstore looking to integrate our order management system with your shipping logistics platform. This document outlines the technical requirements, API endpoints, and workflows necessary for a successful integration.

## 2. General API Requirements
*   **Protocol:** RESTful API over HTTPS.
*   **Data Format:** JSON for both requests and responses.
*   **Authentication:** Secure authentication method (JWT).
*   **Environment:**
    *   **Sandbox/Staging:** A fully functional test environment to develop and test the integration without creating real shipments.
    *   **Production:** The live environment for real transactions.

## 3. Required Endpoints

### 3.1. Calculate Shipping Rates
**Goal:** To show our customers the estimated shipping cost and delivery time before they place an order.
*   **Input:** Origin address, Destination address, Package weight/dimensions.
*   **Output:** List of available services (e.g., Standard, Express), estimated cost, and estimated delivery date.

### 3.2. Create Shipment
**Goal:** To book a shipment and generate a tracking number when an order is confirmed.
*   **Input:**
    *   Sender Details (Name, Address, Phone).
    *   Receiver Details (Name, Address, Phone).
    *   Package Details (Weight, Dimensions, Content Description).
    *   Service Type (Selected from Rate Calculation).
    *   Reference Number (Our Order ID).
*   **Output:** Shipment ID, Tracking Number, Label URL (or ZPL/PDF data).

### 3.3. Print Waybill / Label
**Goal:** To retrieve the shipping label (Waybill) for printing at our warehouse.
*   **Input:** Shipment ID.
*   **Output:** File download (PDF/ZPL) or a URL to the label image.

### 3.4. Track Shipment Status
**Goal:** To show the current status of a package to our customers.
*   **Input:** Tracking Number.
*   **Output:** Current status (e.g., "Picked Up", "In Transit", "Delivered"), timestamp of last update, and history of tracking events.

### 3.5. List Shipments
**Goal:** To view a history of shipments created within a specific timeframe for reconciliation.
*   **Input:** Date Range (Start Date, End Date), Status Filter (optional).
*   **Output:** List of shipments with IDs, Tracking Numbers, Statuses, and Creation Dates.

### 3.6. Cancel Shipment
**Goal:** To void a shipment if an order is cancelled before pickup.
*   **Input:** Shipment ID.
*   **Output:** Confirmation of cancellation and refund of any pre-paid fees (if applicable).

## 4. Webhooks (Real-time Updates)
Instead of us constantly polling your API for status updates, we require a Webhook mechanism.
*   **Event:** `shipment.status_changed`
*   **Payload:** Should include Tracking Number, New Status, Timestamp, and Reference Number.
*   **Requirement:** Ability to register a callback URL where you will push these updates.

## 5. Additional Requirements
*   **Address Validation:** An endpoint to validate the customer's shipping address (city/state/zip match) to prevent delivery failures.
*   **Error Handling:** Clear error codes and messages (e.g., "Invalid Phone Number", "Zip Code not found") to help us debug issues.
*   **Rate Limits:** Please specify any rate limits (requests per minute) for your API.

## 6. Support & Documentation
*   Please provide full technical documentation (Swagger/OpenAPI spec preferred).
*   Access to a technical support contact during the integration phase.