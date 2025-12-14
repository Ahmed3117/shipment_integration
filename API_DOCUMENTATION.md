# Shipping Integration API Documentation

## Overview

This API provides shipping logistics integration for e-commerce platforms. It supports shipment creation, tracking, rate calculation, and webhook notifications.

**Base URL:** `http://localhost:8000/api`

**Authentication:** JWT (JSON Web Token)

**Rate Limits:** 100 requests per minute per user

---

## Integration Flow

This section illustrates the complete flow for an e-commerce platform (e.g., a bookstore) integrating with this Shipping API.

### Phase 1: Initial Setup (One-time)

```
  E-Commerce Developer                             Shipping API
  ────────────────────                             ────────────
         │                                                │
         │  1. Register Account                           │
         │  POST /api/auth/register/                      │
         │  { username, email, password, company_name }   │
         │───────────────────────────────────────────────►│
         │◄───────────────────────────────────────────────│
         │  { user_id, message: "success" }               │
         │                                                │
         │  2. Get API Credentials                        │
         │  POST /api/auth/login/                         │
         │───────────────────────────────────────────────►│
         │◄───────────────────────────────────────────────│
         │  { access_token, refresh_token }               │
         │                                                │
         │  3. Register Webhook (to receive updates)      │
         │  POST /api/webhooks/                           │
         │  { url: "https://yoursite.com/webhook",        │
         │    event: "shipment.status_changed" }          │
         │───────────────────────────────────────────────►│
         │◄───────────────────────────────────────────────│
         │  { webhook_id, secret }                        │
         │                                                │
```

### Phase 2: Customer Checkout Flow

```
  Customer            E-Commerce Website                Shipping API
  ────────            ──────────────────                ────────────
      │                      │                                 │
      │  Adds items to cart  │                                 │
      │─────────────────────►│                                 │
      │                      │                                 │
      │  Enters shipping     │                                 │
      │  address             │                                 │
      │─────────────────────►│                                 │
      │                      │                                 │
      │                      │  4. Validate Address            │
      │                      │  POST /api/address/validate/    │
      │                      │────────────────────────────────►│
      │                      │◄────────────────────────────────│
      │                      │  { is_valid: true }             │
      │                      │                                 │
      │                      │  5. Calculate Rates             │
      │                      │  POST /api/rates/calculate/     │
      │                      │  { origin, destination, weight }│
      │                      │────────────────────────────────►│
      │                      │◄────────────────────────────────│
      │                      │  { rates: [                     │
      │                      │    { Standard: $5, 5-7 days },  │
      │                      │    { Express: $15, 1-2 days }   │
      │                      │  ]}                             │
      │                      │                                 │
      │  Display shipping    │                                 │
      │  options to customer │                                 │
      │◄─────────────────────│                                 │
      │                      │                                 │
      │  Selects "Express"   │                                 │
      │  & completes payment │                                 │
      │─────────────────────►│                                 │
      │                      │                                 │
      │  Order Confirmed!    │                                 │
      │  Order #ORD-9876     │                                 │
      │◄─────────────────────│                                 │
      │                      │                                 │
```

### Phase 3: Order Fulfillment (Warehouse)

```
  Warehouse Staff          E-Commerce System             Shipping API
  ───────────────          ─────────────────             ────────────
         │                        │                              │
         │  Process order         │                              │
         │  ORD-9876              │                              │
         │───────────────────────►│                              │
         │                        │                              │
         │                        │  6. Create Shipment          │
         │                        │  POST /api/shipments/        │
         │                        │  {                           │
         │                        │    reference_number: "ORD-9876",
         │                        │    sender: { warehouse addr },
         │                        │    receiver: { customer addr },
         │                        │    weight: 2.5,              │
         │                        │    service_type: 2 (Express) │
         │                        │  }                           │
         │                        │─────────────────────────────►│
         │                        │◄─────────────────────────────│
         │                        │  {                           │
         │                        │    shipment_id: "uuid...",   │
         │                        │    tracking_number: "SHP123456789012",
         │                        │    label_url: "/shipments/.../label/"
         │                        │  }                           │
         │                        │                              │
         │                        │  7. Get Shipping Label       │
         │                        │  GET /api/shipments/{id}/label/
         │                        │─────────────────────────────►│
         │                        │◄─────────────────────────────│
         │                        │  { PDF/ZPL label data }      │
         │                        │                              │
         │  Print label &         │                              │
         │  attach to package     │                              │
         │◄───────────────────────│                              │
         │                        │                              │
         │                        │  8. Email customer           │
         │                        │  "Your order shipped!        │
         │                        │   Track: SHP123456789012"    │
         │                        │─────────► Customer           │
         │                        │                              │
```

### Phase 4: Package in Transit (Automatic Webhook Updates)

```
  Carrier Scans           Shipping API               E-Commerce System
  ─────────────           ────────────               ─────────────────
       │                         │                            │
       │  Package "Picked up"    │                            │
       │────────────────────────►│                            │
       │                         │                            │
       │                         │  9. Webhook fires          │
       │                         │  POST https://yoursite.com/webhook
       │                         │  {                         │
       │                         │    event: "shipment.status_changed",
       │                         │    tracking_number: "SHP123456789012",
       │                         │    new_status: "picked_up",│
       │                         │    reference_number: "ORD-9876"
       │                         │  }                         │
       │                         │───────────────────────────►│
       │                         │                            │
       │                         │                            │  Update order DB
       │                         │                            │  Email: "Picked up!"
       │                         │                            │
       │  Package "In Transit"   │                            │
       │────────────────────────►│                            │
       │                         │───────────────────────────►│
       │                         │                            │  Email: "In transit"
       │                         │                            │
       │  "Out for Delivery"     │                            │
       │────────────────────────►│                            │
       │                         │───────────────────────────►│
       │                         │                            │  Email: "Out for delivery!"
       │                         │                            │
       │  "Delivered"            │                            │
       │────────────────────────►│                            │
       │                         │───────────────────────────►│
       │                         │                            │  Email: "Delivered!"
       │                         │                            │  Mark order complete
       │                         │                            │
```

### Phase 5: Customer Tracking (Anytime)

```
  Customer              E-Commerce Website             Shipping API
  ────────              ──────────────────             ────────────
      │                        │                              │
      │  "Where's my order?"   │                              │
      │  Clicks tracking link  │                              │
      │───────────────────────►│                              │
      │                        │                              │
      │                        │  10. Track Shipment          │
      │                        │  GET /api/track/SHP123456789012/
      │                        │─────────────────────────────►│
      │                        │◄─────────────────────────────│
      │                        │  {                           │
      │                        │    status: "in_transit",     │
      │                        │    history: [                │
      │                        │      { "picked_up", "Dec 14" },
      │                        │      { "in_transit", "Dec 15" }
      │                        │    ]                         │
      │                        │  }                           │
      │                        │                              │
      │  Shows tracking page   │                              │
      │◄───────────────────────│                              │
      │                        │                              │
```

### API Endpoints Summary by Phase

| Phase | Endpoint | Purpose |
|-------|----------|---------|
| Setup | `POST /api/auth/register/` | Create account |
| Setup | `POST /api/auth/login/` | Get JWT token |
| Setup | `POST /api/webhooks/` | Register webhook URL |
| Checkout | `POST /api/address/validate/` | Validate customer address |
| Checkout | `POST /api/rates/calculate/` | Show shipping options |
| Fulfillment | `POST /api/shipments/` | Book shipment |
| Fulfillment | `GET /api/shipments/{id}/label/` | Get shipping label |
| Tracking | `GET /api/track/{tracking_number}/` | Customer tracking (public) |
| Admin | `GET /api/shipments/` | List/reconcile shipments |
| Admin | `POST /api/shipments/{id}/cancel/` | Cancel shipment |
| Admin | `POST /api/shipments/{id}/status/` | Update shipment status |

---

## Table of Contents

1. [Integration Flow](#integration-flow)
2. [Authentication](#authentication)
   - [Register User](#1-register-user)
   - [Login](#2-login)
   - [Refresh Token](#3-refresh-token)
   - [Get Profile](#4-get-profile)
   - [Update Profile](#5-update-profile)
3. [Services](#services)
   - [List Service Types](#6-list-service-types)
4. [Rates](#rates)
   - [Calculate Shipping Rates](#7-calculate-shipping-rates)
5. [Shipments](#shipments)
   - [Create Shipment](#8-create-shipment)
   - [List Shipments](#9-list-shipments)
   - [Get Shipment Details](#10-get-shipment-details)
   - [Cancel Shipment](#11-cancel-shipment)
   - [Get Shipment Label](#12-get-shipment-label)
   - [Update Shipment Status](#13-update-shipment-status)
6. [Tracking](#tracking)
   - [Track Shipment](#14-track-shipment)
7. [Address Validation](#address-validation)
   - [Validate Address](#15-validate-address)
8. [Webhooks](#webhooks)
   - [Register Webhook](#16-register-webhook)
   - [List Webhooks](#17-list-webhooks)
   - [Get Webhook Details](#18-get-webhook-details)
   - [Update Webhook](#19-update-webhook)
   - [Delete Webhook](#20-delete-webhook)
9. [Error Codes](#error-codes)

---

## Authentication

All endpoints (except Register, Login, and Track Shipment) require a valid JWT token in the Authorization header.

### 1. Register User

**Description:** Create a new user account.

| Property | Value |
|----------|-------|
| **URL** | `/api/auth/register/` |
| **Method** | `POST` |
| **Auth Required** | No |

**Headers:**

| Header | Value |
|--------|-------|
| Content-Type | application/json |

**Request Body:**

```json
{
    "username": "testuser",
    "email": "testuser@example.com",
    "password": "SecurePass123!",
    "password_confirm": "SecurePass123!",
    "company_name": "Test Company",
    "phone": "1234567890"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| username | string | Yes | Unique username |
| email | string | Yes | Valid email address |
| password | string | Yes | Password (min 8 chars, mixed case, numbers) |
| password_confirm | string | Yes | Must match password |
| company_name | string | No | Company name |
| phone | string | No | Phone number |

**Success Response (201 Created):**

```json
{
    "message": "User registered successfully.",
    "user": {
        "id": 1,
        "username": "testuser",
        "email": "testuser@example.com",
        "company_name": "Test Company",
        "phone": "1234567890"
    }
}
```

**Validation Messages:**

| Error | Message |
|-------|---------|
| Password mismatch | `{"password_confirm": ["Passwords do not match."]}` |
| Weak password | `{"password": ["This password is too common."]}` |
| Duplicate username | `{"username": ["A user with that username already exists."]}` |
| Invalid email | `{"email": ["Enter a valid email address."]}` |

---

### 2. Login

**Description:** Authenticate user and obtain JWT tokens.

| Property | Value |
|----------|-------|
| **URL** | `/api/auth/login/` |
| **Method** | `POST` |
| **Auth Required** | No |

**Headers:**

| Header | Value |
|--------|-------|
| Content-Type | application/json |

**Request Body:**

```json
{
    "username": "testuser",
    "password": "SecurePass123!"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| username | string | Yes | Username |
| password | string | Yes | Password |

**Success Response (200 OK):**

```json
{
    "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
    "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
}
```

**Validation Messages:**

| Error | Message |
|-------|---------|
| Invalid credentials | `{"detail": "No active account found with the given credentials"}` |

---

### 3. Refresh Token

**Description:** Obtain a new access token using refresh token.

| Property | Value |
|----------|-------|
| **URL** | `/api/auth/token/refresh/` |
| **Method** | `POST` |
| **Auth Required** | No |

**Headers:**

| Header | Value |
|--------|-------|
| Content-Type | application/json |

**Request Body:**

```json
{
    "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
}
```

**Success Response (200 OK):**

```json
{
    "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
}
```

**Validation Messages:**

| Error | Message |
|-------|---------|
| Invalid token | `{"detail": "Token is invalid or expired", "code": "token_not_valid"}` |

---

### 4. Get Profile

**Description:** Retrieve current user profile.

| Property | Value |
|----------|-------|
| **URL** | `/api/auth/profile/` |
| **Method** | `GET` |
| **Auth Required** | Yes |

**Headers:**

| Header | Value |
|--------|-------|
| Authorization | Bearer {access_token} |

**Success Response (200 OK):**

```json
{
    "id": 1,
    "username": "testuser",
    "email": "testuser@example.com",
    "company_name": "Test Company",
    "phone": "1234567890"
}
```

---

### 5. Update Profile

**Description:** Update current user profile.

| Property | Value |
|----------|-------|
| **URL** | `/api/auth/profile/` |
| **Method** | `PATCH` |
| **Auth Required** | Yes |

**Headers:**

| Header | Value |
|--------|-------|
| Authorization | Bearer {access_token} |
| Content-Type | application/json |

**Request Body:**

```json
{
    "company_name": "Updated Company Name",
    "phone": "9876543210"
}
```

**Success Response (200 OK):**

```json
{
    "id": 1,
    "username": "testuser",
    "email": "testuser@example.com",
    "company_name": "Updated Company Name",
    "phone": "9876543210"
}
```

---

## Services

### 6. List Service Types

**Description:** Get all available shipping service types.

| Property | Value |
|----------|-------|
| **URL** | `/api/services/` |
| **Method** | `GET` |
| **Auth Required** | Yes |

**Headers:**

| Header | Value |
|--------|-------|
| Authorization | Bearer {access_token} |

**Success Response (200 OK):**

```json
[
    {
        "id": 1,
        "name": "Standard",
        "code": "STD",
        "base_rate": "10.00",
        "rate_per_kg": "2.50",
        "estimated_days_min": 5,
        "estimated_days_max": 7
    },
    {
        "id": 2,
        "name": "Express",
        "code": "EXP",
        "base_rate": "25.00",
        "rate_per_kg": "5.00",
        "estimated_days_min": 1,
        "estimated_days_max": 3
    }
]
```

---

## Rates

### 7. Calculate Shipping Rates

**Description:** Calculate shipping rates based on origin, destination, and package details.

| Property | Value |
|----------|-------|
| **URL** | `/api/rates/calculate/` |
| **Method** | `POST` |
| **Auth Required** | Yes |

**Headers:**

| Header | Value |
|--------|-------|
| Authorization | Bearer {access_token} |
| Content-Type | application/json |

**Request Body:**

```json
{
    "origin_city": "New York",
    "origin_state": "NY",
    "origin_zip_code": "10001",
    "origin_country": "USA",
    "destination_city": "Los Angeles",
    "destination_state": "CA",
    "destination_zip_code": "90001",
    "destination_country": "USA",
    "weight": 5.5,
    "length": 30,
    "width": 20,
    "height": 15
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| origin_city | string | Yes | Origin city |
| origin_state | string | Yes | Origin state |
| origin_zip_code | string | Yes | Origin postal code |
| origin_country | string | No | Origin country (default: USA) |
| destination_city | string | Yes | Destination city |
| destination_state | string | Yes | Destination state |
| destination_zip_code | string | Yes | Destination postal code |
| destination_country | string | No | Destination country (default: USA) |
| weight | decimal | Yes | Package weight in kg (min: 0.01) |
| length | decimal | Yes | Package length in cm (min: 0.01) |
| width | decimal | Yes | Package width in cm (min: 0.01) |
| height | decimal | Yes | Package height in cm (min: 0.01) |

**Success Response (200 OK):**

```json
{
    "origin": {
        "city": "New York",
        "state": "NY",
        "zip_code": "10001",
        "country": "USA"
    },
    "destination": {
        "city": "Los Angeles",
        "state": "CA",
        "zip_code": "90001",
        "country": "USA"
    },
    "package": {
        "weight": "5.5",
        "length": "30",
        "width": "20",
        "height": "15"
    },
    "rates": [
        {
            "service_id": 1,
            "service_name": "Standard",
            "service_code": "STD",
            "estimated_cost": "23.75",
            "estimated_delivery_date_min": "2024-12-18",
            "estimated_delivery_date_max": "2024-12-20"
        },
        {
            "service_id": 2,
            "service_name": "Express",
            "service_code": "EXP",
            "estimated_cost": "52.50",
            "estimated_delivery_date_min": "2024-12-14",
            "estimated_delivery_date_max": "2024-12-16"
        }
    ]
}
```

**Validation Messages:**

| Error | Message |
|-------|---------|
| Invalid weight | `{"weight": ["Ensure this value is greater than or equal to 0.01."]}` |
| Missing field | `{"origin_city": ["This field is required."]}` |

---

## Shipments

### 8. Create Shipment

**Description:** Create a new shipment and generate tracking number.

| Property | Value |
|----------|-------|
| **URL** | `/api/shipments/` |
| **Method** | `POST` |
| **Auth Required** | Yes |

**Headers:**

| Header | Value |
|--------|-------|
| Authorization | Bearer {access_token} |
| Content-Type | application/json |

**Request Body:**

```json
{
    "reference_number": "ORDER-12345",
    "sender_address": {
        "name": "John Sender",
        "street": "123 Main St",
        "city": "New York",
        "state": "NY",
        "zip_code": "10001",
        "country": "USA",
        "phone": "1234567890"
    },
    "receiver_address": {
        "name": "Jane Receiver",
        "street": "456 Oak Ave",
        "city": "Los Angeles",
        "state": "CA",
        "zip_code": "90001",
        "country": "USA",
        "phone": "0987654321"
    },
    "weight": 5.5,
    "length": 30,
    "width": 20,
    "height": 15,
    "content_description": "Books - Fiction novels",
    "service_type": 1
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| reference_number | string | No | Your order ID |
| sender_address | object | Yes | Sender address details |
| receiver_address | object | Yes | Receiver address details |
| weight | decimal | Yes | Package weight in kg |
| length | decimal | Yes | Package length in cm |
| width | decimal | Yes | Package width in cm |
| height | decimal | Yes | Package height in cm |
| content_description | string | No | Description of contents |
| service_type | integer | Yes | Service type ID |

**Address Object:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| name | string | Yes | Contact name |
| street | string | Yes | Street address |
| city | string | Yes | City |
| state | string | Yes | State/Province |
| zip_code | string | Yes | Postal code |
| country | string | No | Country (default: USA) |
| phone | string | Yes | Phone number (min 10 digits) |

**Success Response (201 Created):**

```json
{
    "message": "Shipment created successfully.",
    "shipment": {
        "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "tracking_number": "SHP123456789012",
        "reference_number": "ORDER-12345",
        "sender_address": {
            "id": 1,
            "name": "John Sender",
            "street": "123 Main St",
            "city": "New York",
            "state": "NY",
            "zip_code": "10001",
            "country": "USA",
            "phone": "1234567890"
        },
        "receiver_address": {
            "id": 2,
            "name": "Jane Receiver",
            "street": "456 Oak Ave",
            "city": "Los Angeles",
            "state": "CA",
            "zip_code": "90001",
            "country": "USA",
            "phone": "0987654321"
        },
        "weight": "5.50",
        "length": "30.00",
        "width": "20.00",
        "height": "15.00",
        "content_description": "Books - Fiction novels",
        "service_type": {
            "id": 1,
            "name": "Standard",
            "code": "STD"
        },
        "estimated_cost": "23.75",
        "estimated_delivery_date": "2024-12-20",
        "status": "confirmed",
        "label_url": "/api/shipments/a1b2c3d4-e5f6-7890-abcd-ef1234567890/label/",
        "created_at": "2024-12-13T10:30:00Z",
        "updated_at": "2024-12-13T10:30:00Z"
    }
}
```

**Validation Messages:**

| Error | Message |
|-------|---------|
| Invalid phone | `{"sender_address": {"phone": ["Invalid phone number. Must have at least 10 digits."]}}` |
| Invalid zip | `{"receiver_address": {"zip_code": ["Zip code not found."]}}` |
| Invalid weight | `{"weight": ["Weight must be greater than 0."]}` |
| Weight too high | `{"weight": ["Weight cannot exceed 1000 kg."]}` |
| Invalid service | `{"service_type": ["Invalid pk \"99\" - object does not exist."]}` |

---

### 9. List Shipments

**Description:** List shipments with optional filters.

| Property | Value |
|----------|-------|
| **URL** | `/api/shipments/` |
| **Method** | `GET` |
| **Auth Required** | Yes |

**Headers:**

| Header | Value |
|--------|-------|
| Authorization | Bearer {access_token} |

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| start_date | date | No | Filter by start date (YYYY-MM-DD) |
| end_date | date | No | Filter by end date (YYYY-MM-DD) |
| status | string | No | Filter by status |
| page | integer | No | Page number for pagination |

**Success Response (200 OK):**

```json
{
    "count": 25,
    "next": "http://localhost:8000/api/shipments/?page=2",
    "previous": null,
    "results": [
        {
            "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "tracking_number": "SHP123456789012",
            "reference_number": "ORDER-12345",
            "status": "confirmed",
            "service_type": {
                "id": 1,
                "name": "Standard",
                "code": "STD"
            },
            "estimated_cost": "23.75",
            "created_at": "2024-12-13T10:30:00Z"
        }
    ]
}
```

---

### 10. Get Shipment Details

**Description:** Get detailed information about a specific shipment.

| Property | Value |
|----------|-------|
| **URL** | `/api/shipments/{shipment_id}/` |
| **Method** | `GET` |
| **Auth Required** | Yes |

**Headers:**

| Header | Value |
|--------|-------|
| Authorization | Bearer {access_token} |

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| shipment_id | uuid | Yes | Shipment UUID |

**Success Response (200 OK):**

```json
{
    "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "tracking_number": "SHP123456789012",
    "reference_number": "ORDER-12345",
    "sender_address": { ... },
    "receiver_address": { ... },
    "weight": "5.50",
    "length": "30.00",
    "width": "20.00",
    "height": "15.00",
    "content_description": "Books - Fiction novels",
    "service_type": { ... },
    "estimated_cost": "23.75",
    "estimated_delivery_date": "2024-12-20",
    "status": "confirmed",
    "label_url": "/api/shipments/a1b2c3d4-e5f6-7890-abcd-ef1234567890/label/",
    "created_at": "2024-12-13T10:30:00Z",
    "updated_at": "2024-12-13T10:30:00Z"
}
```

**Error Response (404 Not Found):**

```json
{
    "detail": "Not found."
}
```

---

### 11. Cancel Shipment

**Description:** Cancel a shipment before pickup.

| Property | Value |
|----------|-------|
| **URL** | `/api/shipments/{shipment_id}/cancel/` |
| **Method** | `POST` |
| **Auth Required** | Yes |

**Headers:**

| Header | Value |
|--------|-------|
| Authorization | Bearer {access_token} |

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| shipment_id | uuid | Yes | Shipment UUID |

**Success Response (200 OK):**

```json
{
    "message": "Shipment cancelled successfully.",
    "shipment_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "tracking_number": "SHP123456789012",
    "refund_status": "Refund will be processed within 3-5 business days."
}
```

**Error Responses:**

| Status | Response |
|--------|----------|
| 400 | `{"error": "Cannot cancel shipment with status: delivered"}` |
| 400 | `{"error": "Cannot cancel shipment that is already in transit. Please contact support."}` |

---

### 12. Get Shipment Label

**Description:** Retrieve shipping label (waybill) for printing.

| Property | Value |
|----------|-------|
| **URL** | `/api/shipments/{shipment_id}/label/` |
| **Method** | `GET` |
| **Auth Required** | Yes |

**Headers:**

| Header | Value |
|--------|-------|
| Authorization | Bearer {access_token} |

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| shipment_id | uuid | Yes | Shipment UUID |

**Success Response (200 OK):**

```json
{
    "shipment_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "tracking_number": "SHP123456789012",
    "label_format": "PDF",
    "label_url": "/api/shipments/a1b2c3d4-e5f6-7890-abcd-ef1234567890/label/download/",
    "label_zpl": null
}
```

**Error Response (400 Bad Request):**

```json
{
    "error": "Cannot generate label for cancelled shipment."
}
```

---

## Tracking

### 13. Track Shipment

**Description:** Track a shipment by tracking number (public endpoint).

| Property | Value |
|----------|-------|
| **URL** | `/api/track/{tracking_number}/` |
| **Method** | `GET` |
| **Auth Required** | No |

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| tracking_number | string | Yes | Shipment tracking number |

**Success Response (200 OK):**

```json
{
    "tracking_number": "SHP123456789012",
    "current_status": "in_transit",
    "last_update": "2024-12-14T15:30:00Z",
    "reference_number": "ORDER-12345",
    "estimated_delivery_date": "2024-12-20",
    "history": [
        {
            "id": 3,
            "status": "in_transit",
            "description": "Package is in transit to destination.",
            "location": "Chicago, IL",
            "timestamp": "2024-12-14T15:30:00Z"
        },
        {
            "id": 2,
            "status": "picked_up",
            "description": "Package picked up by carrier.",
            "location": "New York, NY",
            "timestamp": "2024-12-13T14:00:00Z"
        },
        {
            "id": 1,
            "status": "confirmed",
            "description": "Shipment created and confirmed.",
            "location": "New York, NY",
            "timestamp": "2024-12-13T10:30:00Z"
        }
    ]
}
```

**Error Response (404 Not Found):**

```json
{
    "detail": "Not found."
}
```

---

## Address Validation

### 14. Validate Address

**Description:** Validate a shipping address to prevent delivery failures.

| Property | Value |
|----------|-------|
| **URL** | `/api/address/validate/` |
| **Method** | `POST` |
| **Auth Required** | Yes |

**Headers:**

| Header | Value |
|--------|-------|
| Authorization | Bearer {access_token} |
| Content-Type | application/json |

**Request Body:**

```json
{
    "street": "123 Main St",
    "city": "New York",
    "state": "NY",
    "zip_code": "10001",
    "country": "USA"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| street | string | No | Street address |
| city | string | Yes | City |
| state | string | Yes | State/Province |
| zip_code | string | Yes | Postal code |
| country | string | No | Country (default: USA) |

**Success Response (200 OK) - Valid Address:**

```json
{
    "is_valid": true,
    "message": "Address is valid.",
    "suggested_address": {
        "street": "123 Main St",
        "city": "New York",
        "state": "NY",
        "zip_code": "10001",
        "country": "USA"
    }
}
```

**Success Response (200 OK) - Invalid Address:**

```json
{
    "is_valid": false,
    "message": "Zip code not found.",
    "suggested_address": null
}
```

---

## Webhooks

### 15. Register Webhook

**Description:** Register a callback URL for status update notifications.

| Property | Value |
|----------|-------|
| **URL** | `/api/webhooks/` |
| **Method** | `POST` |
| **Auth Required** | Yes |

**Headers:**

| Header | Value |
|--------|-------|
| Authorization | Bearer {access_token} |
| Content-Type | application/json |

**Request Body:**

```json
{
    "url": "https://your-domain.com/webhooks/shipping",
    "event": "shipment.status_changed",
    "is_active": true
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| url | string | Yes | HTTPS callback URL |
| event | string | Yes | Event type |
| is_active | boolean | No | Whether webhook is active (default: true) |

**Available Events:**

| Event | Description |
|-------|-------------|
| shipment.status_changed | Triggered when shipment status changes |
| shipment.created | Triggered when shipment is created |
| shipment.delivered | Triggered when shipment is delivered |

**Success Response (201 Created):**

```json
{
    "message": "Webhook registered successfully.",
    "webhook": {
        "id": 1,
        "url": "https://your-domain.com/webhooks/shipping",
        "event": "shipment.status_changed",
        "is_active": true,
        "created_at": "2024-12-13T10:30:00Z"
    }
}
```

**Validation Messages:**

| Error | Message |
|-------|---------|
| Invalid URL | `{"url": ["Webhook URL must use HTTPS."]}` |
| Invalid event | `{"event": ["\"invalid\" is not a valid choice."]}` |

**Webhook Payload (sent to your URL):**

```json
{
    "event": "shipment.status_changed",
    "tracking_number": "SHP123456789012",
    "new_status": "in_transit",
    "reference_number": "ORDER-12345",
    "timestamp": "2024-12-14T15:30:00Z"
}
```

---

### 16. List Webhooks

**Description:** List all registered webhooks.

| Property | Value |
|----------|-------|
| **URL** | `/api/webhooks/` |
| **Method** | `GET` |
| **Auth Required** | Yes |

**Headers:**

| Header | Value |
|--------|-------|
| Authorization | Bearer {access_token} |

**Success Response (200 OK):**

```json
[
    {
        "id": 1,
        "url": "https://your-domain.com/webhooks/shipping",
        "event": "shipment.status_changed",
        "is_active": true,
        "created_at": "2024-12-13T10:30:00Z"
    }
]
```

---

### 17. Get Webhook Details

**Description:** Get details of a specific webhook.

| Property | Value |
|----------|-------|
| **URL** | `/api/webhooks/{webhook_id}/` |
| **Method** | `GET` |
| **Auth Required** | Yes |

**Headers:**

| Header | Value |
|--------|-------|
| Authorization | Bearer {access_token} |

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| webhook_id | integer | Yes | Webhook ID |

**Success Response (200 OK):**

```json
{
    "id": 1,
    "url": "https://your-domain.com/webhooks/shipping",
    "event": "shipment.status_changed",
    "is_active": true,
    "created_at": "2024-12-13T10:30:00Z"
}
```

---

### 18. Update Webhook

**Description:** Update a webhook configuration.

| Property | Value |
|----------|-------|
| **URL** | `/api/webhooks/{webhook_id}/` |
| **Method** | `PATCH` |
| **Auth Required** | Yes |

**Headers:**

| Header | Value |
|--------|-------|
| Authorization | Bearer {access_token} |
| Content-Type | application/json |

**Request Body:**

```json
{
    "is_active": false
}
```

**Success Response (200 OK):**

```json
{
    "id": 1,
    "url": "https://your-domain.com/webhooks/shipping",
    "event": "shipment.status_changed",
    "is_active": false,
    "created_at": "2024-12-13T10:30:00Z"
}
```

---

### 19. Delete Webhook

**Description:** Delete a webhook.

| Property | Value |
|----------|-------|
| **URL** | `/api/webhooks/{webhook_id}/` |
| **Method** | `DELETE` |
| **Auth Required** | Yes |

**Headers:**

| Header | Value |
|--------|-------|
| Authorization | Bearer {access_token} |

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| webhook_id | integer | Yes | Webhook ID |

**Success Response (200 OK):**

```json
{
    "message": "Webhook deleted successfully."
}
```

---

## Error Codes

### HTTP Status Codes

| Code | Description |
|------|-------------|
| 200 | OK - Request successful |
| 201 | Created - Resource created successfully |
| 400 | Bad Request - Invalid request data |
| 401 | Unauthorized - Missing or invalid token |
| 403 | Forbidden - Permission denied |
| 404 | Not Found - Resource not found |
| 429 | Too Many Requests - Rate limit exceeded |
| 500 | Internal Server Error - Server error |

### Common Error Response Format

```json
{
    "detail": "Error message here"
}
```

Or for validation errors:

```json
{
    "field_name": ["Error message for this field."]
}
```

### Authentication Errors

| Error | Response |
|-------|----------|
| Missing token | `{"detail": "Authentication credentials were not provided."}` |
| Invalid token | `{"detail": "Given token not valid for any token type", "code": "token_not_valid"}` |
| Expired token | `{"detail": "Token is invalid or expired", "code": "token_not_valid"}` |

---

## Shipment Status Values

| Status | Description |
|--------|-------------|
| pending | Shipment created, awaiting confirmation |
| confirmed | Shipment confirmed and label generated |
| picked_up | Package picked up by carrier |
| in_transit | Package in transit to destination |
| out_for_delivery | Package out for delivery |
| delivered | Package delivered successfully |
| cancelled | Shipment cancelled |
| returned | Package returned to sender |

---
