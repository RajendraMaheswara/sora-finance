// Package docs contains forecast-only Swagger documentation.
package docs

import "github.com/swaggo/swag"

const docTemplate = `{
    "swagger": "2.0",
    "info": {
        "description": "Forecast-only API documentation. Forecast source of truth: forecast_runs + forecast_results. Forecast write endpoints are internal-service only. Latest forecast is only exposed after a successful run has saved at least one forecast_result.",
        "title": "Sora Finance Forecast API",
        "version": "1.3"
    },
    "host": "localhost:8080",
    "basePath": "/",
    "schemes": [
        "http"
    ],
    "paths": {
        "/api/forecast/latest": {
            "get": {
                "summary": "Get latest forecast",
                "description": "Mengambil latest successful forecast dari forecast_runs + forecast_results. It never returns a run that has zero forecast_results.",
                "tags": [
                    "Forecast Core"
                ],
                "produces": [
                    "application/json"
                ],
                "parameters": [
                    {
                        "type": "string",
                        "description": "Bearer JWT token",
                        "name": "Authorization",
                        "in": "header",
                        "required": true
                    },
                    {
                        "name": "forecast_type",
                        "in": "query",
                        "required": false,
                        "type": "string",
                        "enum": [
                            "visitors",
                            "sales",
                            "inventory"
                        ],
                        "default": "visitors"
                    },
                    {
                        "name": "horizon_label",
                        "in": "query",
                        "required": false,
                        "type": "string",
                        "enum": [
                            "daily",
                            "weekly",
                            "monthly"
                        ],
                        "default": "daily"
                    },
                    {
                        "name": "store_id",
                        "in": "query",
                        "required": false,
                        "type": "string",
                        "format": "uuid",
                        "description": "Only system admin can request another store explicitly."
                    }
                ],
                "responses": {
                    "200": {
                        "description": "OK",
                        "schema": {
                            "$ref": "#/definitions/ForecastLatestResponse"
                        }
                    },
                    "400": {
                        "description": "Bad Request",
                        "schema": {
                            "$ref": "#/definitions/ErrorResponse"
                        }
                    },
                    "401": {
                        "description": "Unauthorized",
                        "schema": {
                            "$ref": "#/definitions/ErrorResponse"
                        }
                    },
                    "404": {
                        "description": "Not Found",
                        "schema": {
                            "$ref": "#/definitions/ErrorResponse"
                        }
                    },
                    "500": {
                        "description": "Internal Server Error",
                        "schema": {
                            "$ref": "#/definitions/ErrorResponse"
                        }
                    }
                }
            }
        },
        "/api/forecast/visitors/latest": {
            "get": {
                "summary": "Get latest visitors forecast",
                "description": "Shortcut latest forecast untuk forecast_type=visitors. It never returns a run that has zero forecast_results.",
                "tags": [
                    "Forecast Core"
                ],
                "produces": [
                    "application/json"
                ],
                "parameters": [
                    {
                        "type": "string",
                        "description": "Bearer JWT token",
                        "name": "Authorization",
                        "in": "header",
                        "required": true
                    },
                    {
                        "name": "horizon_label",
                        "in": "query",
                        "required": false,
                        "type": "string",
                        "enum": [
                            "daily",
                            "weekly",
                            "monthly"
                        ],
                        "default": "daily"
                    },
                    {
                        "name": "store_id",
                        "in": "query",
                        "required": false,
                        "type": "string",
                        "format": "uuid",
                        "description": "Only system admin can request another store explicitly."
                    }
                ],
                "responses": {
                    "200": {
                        "description": "OK",
                        "schema": {
                            "$ref": "#/definitions/ForecastLatestResponse"
                        }
                    },
                    "400": {
                        "description": "Bad Request",
                        "schema": {
                            "$ref": "#/definitions/ErrorResponse"
                        }
                    },
                    "401": {
                        "description": "Unauthorized",
                        "schema": {
                            "$ref": "#/definitions/ErrorResponse"
                        }
                    },
                    "404": {
                        "description": "Not Found",
                        "schema": {
                            "$ref": "#/definitions/ErrorResponse"
                        }
                    },
                    "500": {
                        "description": "Internal Server Error",
                        "schema": {
                            "$ref": "#/definitions/ErrorResponse"
                        }
                    }
                }
            }
        },
        "/api/forecast-runs/{id}": {
            "get": {
                "summary": "Get forecast run by ID",
                "description": "Mengambil satu forecast run dari forecast_runs.",
                "tags": [
                    "Forecast Core"
                ],
                "produces": [
                    "application/json"
                ],
                "parameters": [
                    {
                        "type": "string",
                        "description": "Bearer JWT token",
                        "name": "Authorization",
                        "in": "header",
                        "required": true
                    },
                    {
                        "name": "id",
                        "in": "path",
                        "required": true,
                        "type": "integer",
                        "format": "int64"
                    }
                ],
                "responses": {
                    "200": {
                        "description": "OK",
                        "schema": {
                            "$ref": "#/definitions/ForecastRun"
                        }
                    },
                    "400": {
                        "description": "Bad Request",
                        "schema": {
                            "$ref": "#/definitions/ErrorResponse"
                        }
                    },
                    "401": {
                        "description": "Unauthorized",
                        "schema": {
                            "$ref": "#/definitions/ErrorResponse"
                        }
                    },
                    "404": {
                        "description": "Not Found",
                        "schema": {
                            "$ref": "#/definitions/ErrorResponse"
                        }
                    },
                    "500": {
                        "description": "Internal Server Error",
                        "schema": {
                            "$ref": "#/definitions/ErrorResponse"
                        }
                    }
                }
            }
        },
        "/api/forecast-results": {
            "get": {
                "summary": "Get forecast results",
                "description": "Mengambil daftar forecast_results, scoped by store untuk user non-admin.",
                "tags": [
                    "Forecast Core"
                ],
                "produces": [
                    "application/json"
                ],
                "parameters": [
                    {
                        "type": "string",
                        "description": "Bearer JWT token",
                        "name": "Authorization",
                        "in": "header",
                        "required": true
                    }
                ],
                "responses": {
                    "200": {
                        "description": "OK",
                        "schema": {
                            "type": "array",
                            "items": {
                                "$ref": "#/definitions/ForecastResult"
                            }
                        }
                    },
                    "401": {
                        "description": "Unauthorized",
                        "schema": {
                            "$ref": "#/definitions/ErrorResponse"
                        }
                    },
                    "500": {
                        "description": "Internal Server Error",
                        "schema": {
                            "$ref": "#/definitions/ErrorResponse"
                        }
                    }
                }
            }
        },
        "/api/forecast-results/{id}": {
            "get": {
                "summary": "Get forecast result by ID",
                "description": "Mengambil satu forecast result berdasarkan ID.",
                "tags": [
                    "Forecast Core"
                ],
                "produces": [
                    "application/json"
                ],
                "parameters": [
                    {
                        "type": "string",
                        "description": "Bearer JWT token",
                        "name": "Authorization",
                        "in": "header",
                        "required": true
                    },
                    {
                        "name": "id",
                        "in": "path",
                        "required": true,
                        "type": "integer",
                        "format": "int64"
                    }
                ],
                "responses": {
                    "200": {
                        "description": "OK",
                        "schema": {
                            "$ref": "#/definitions/ForecastResult"
                        }
                    },
                    "400": {
                        "description": "Bad Request",
                        "schema": {
                            "$ref": "#/definitions/ErrorResponse"
                        }
                    },
                    "401": {
                        "description": "Unauthorized",
                        "schema": {
                            "$ref": "#/definitions/ErrorResponse"
                        }
                    },
                    "404": {
                        "description": "Not Found",
                        "schema": {
                            "$ref": "#/definitions/ErrorResponse"
                        }
                    },
                    "500": {
                        "description": "Internal Server Error",
                        "schema": {
                            "$ref": "#/definitions/ErrorResponse"
                        }
                    }
                }
            }
        },
        "/internal/forecast/save": {
            "post": {
                "summary": "Save forecast run and results atomically (internal service)",
                "description": "Recommended internal endpoint for forecast-service. Validates run + non-empty results, inserts forecast_runs and forecast_results in one transaction, then marks the run as latest only after results are saved successfully.",
                "tags": [
                    "Forecast Core"
                ],
                "consumes": [
                    "application/json"
                ],
                "produces": [
                    "application/json"
                ],
                "parameters": [
                    {
                        "type": "string",
                        "description": "Internal forecast service key. Backend also accepts Authorization: Bearer <INTERNAL_SERVICE_KEY>.",
                        "name": "X-Service-Key",
                        "in": "header",
                        "required": true
                    },
                    {
                        "type": "string",
                        "description": "Optional alternative to X-Service-Key: Bearer <INTERNAL_SERVICE_KEY>.",
                        "name": "Authorization",
                        "in": "header",
                        "required": false
                    },
                    {
                        "name": "body",
                        "in": "body",
                        "required": true,
                        "schema": {
                            "$ref": "#/definitions/ForecastSaveInput"
                        }
                    }
                ],
                "responses": {
                    "201": {
                        "description": "Created",
                        "schema": {
                            "$ref": "#/definitions/ForecastSaveResponse"
                        }
                    },
                    "400": {
                        "description": "Bad Request",
                        "schema": {
                            "$ref": "#/definitions/ErrorResponse"
                        }
                    },
                    "401": {
                        "description": "Unauthorized",
                        "schema": {
                            "$ref": "#/definitions/ErrorResponse"
                        }
                    },
                    "403": {
                        "description": "Forbidden",
                        "schema": {
                            "$ref": "#/definitions/ErrorResponse"
                        }
                    },
                    "500": {
                        "description": "Internal Server Error",
                        "schema": {
                            "$ref": "#/definitions/ErrorResponse"
                        }
                    }
                }
            }
        },
        "/internal/forecast/visitors-daily-history": {
            "get": {
                "summary": "Get visitors daily history",
                "description": "Endpoint internal untuk forecast-service mengambil data historis visitors harian dari orders/order_items.",
                "tags": [
                    "Forecast Historical Data"
                ],
                "produces": [
                    "application/json"
                ],
                "parameters": [
                    {
                        "type": "string",
                        "description": "Internal forecast service key. Backend also accepts Authorization: Bearer <INTERNAL_SERVICE_KEY>.",
                        "name": "X-Service-Key",
                        "in": "header",
                        "required": true
                    },
                    {
                        "type": "string",
                        "description": "Optional alternative to X-Service-Key: Bearer <INTERNAL_SERVICE_KEY>.",
                        "name": "Authorization",
                        "in": "header",
                        "required": false
                    },
                    {
                        "name": "store_id",
                        "in": "query",
                        "required": true,
                        "type": "string",
                        "format": "uuid"
                    }
                ],
                "responses": {
                    "200": {
                        "description": "OK",
                        "schema": {
                            "type": "array",
                            "items": {
                                "$ref": "#/definitions/VisitorsDailyHistoryRow"
                            }
                        }
                    },
                    "400": {
                        "description": "Bad Request",
                        "schema": {
                            "$ref": "#/definitions/ErrorResponse"
                        }
                    },
                    "500": {
                        "description": "Internal Server Error",
                        "schema": {
                            "$ref": "#/definitions/ErrorResponse"
                        }
                    }
                }
            }
        },
        "/internal/forecast/forecast-runs/{id}": {
            "get": {
                "summary": "Get forecast run by ID",
                "description": "Mengambil satu forecast run dari forecast_runs.",
                "tags": [
                    "Forecast Core"
                ],
                "produces": [
                    "application/json"
                ],
                "parameters": [
                    {
                        "type": "string",
                        "description": "Internal forecast service key. Backend also accepts Authorization: Bearer <INTERNAL_SERVICE_KEY>.",
                        "name": "X-Service-Key",
                        "in": "header",
                        "required": true
                    },
                    {
                        "type": "string",
                        "description": "Optional alternative to X-Service-Key: Bearer <INTERNAL_SERVICE_KEY>.",
                        "name": "Authorization",
                        "in": "header",
                        "required": false
                    },
                    {
                        "name": "id",
                        "in": "path",
                        "required": true,
                        "type": "integer",
                        "format": "int64"
                    }
                ],
                "responses": {
                    "200": {
                        "description": "OK",
                        "schema": {
                            "$ref": "#/definitions/ForecastRun"
                        }
                    },
                    "400": {
                        "description": "Bad Request",
                        "schema": {
                            "$ref": "#/definitions/ErrorResponse"
                        }
                    },
                    "401": {
                        "description": "Unauthorized",
                        "schema": {
                            "$ref": "#/definitions/ErrorResponse"
                        }
                    },
                    "404": {
                        "description": "Not Found",
                        "schema": {
                            "$ref": "#/definitions/ErrorResponse"
                        }
                    },
                    "500": {
                        "description": "Internal Server Error",
                        "schema": {
                            "$ref": "#/definitions/ErrorResponse"
                        }
                    }
                }
            }
        },
        "/internal/forecast/forecast-runs": {
            "post": {
                "summary": "Create forecast run header only (internal service)",
                "description": "Compatibility endpoint for older forecast-service flow. It creates forecast_runs with is_latest=false even when status=success. The run becomes latest only after /internal/forecast/forecast-results successfully saves at least one result.",
                "tags": [
                    "Forecast Core"
                ],
                "consumes": [
                    "application/json"
                ],
                "produces": [
                    "application/json"
                ],
                "parameters": [
                    {
                        "type": "string",
                        "description": "Internal forecast service key. Backend also accepts Authorization: Bearer <INTERNAL_SERVICE_KEY>.",
                        "name": "X-Service-Key",
                        "in": "header",
                        "required": true
                    },
                    {
                        "type": "string",
                        "description": "Optional alternative to X-Service-Key: Bearer <INTERNAL_SERVICE_KEY>.",
                        "name": "Authorization",
                        "in": "header",
                        "required": false
                    },
                    {
                        "name": "body",
                        "in": "body",
                        "required": true,
                        "schema": {
                            "$ref": "#/definitions/ForecastRunInput"
                        }
                    }
                ],
                "responses": {
                    "201": {
                        "description": "Created",
                        "schema": {
                            "$ref": "#/definitions/ForecastRunCreateResponse"
                        }
                    },
                    "400": {
                        "description": "Bad Request",
                        "schema": {
                            "$ref": "#/definitions/ErrorResponse"
                        }
                    },
                    "401": {
                        "description": "Unauthorized",
                        "schema": {
                            "$ref": "#/definitions/ErrorResponse"
                        }
                    },
                    "403": {
                        "description": "Forbidden",
                        "schema": {
                            "$ref": "#/definitions/ErrorResponse"
                        }
                    },
                    "500": {
                        "description": "Internal Server Error",
                        "schema": {
                            "$ref": "#/definitions/ErrorResponse"
                        }
                    }
                }
            }
        },
        "/internal/forecast/forecast-results": {
            "get": {
                "summary": "Get forecast results",
                "description": "Mengambil daftar forecast_results, scoped by store untuk user non-admin.",
                "tags": [
                    "Forecast Core"
                ],
                "produces": [
                    "application/json"
                ],
                "parameters": [
                    {
                        "type": "string",
                        "description": "Internal forecast service key. Backend also accepts Authorization: Bearer <INTERNAL_SERVICE_KEY>.",
                        "name": "X-Service-Key",
                        "in": "header",
                        "required": true
                    },
                    {
                        "type": "string",
                        "description": "Optional alternative to X-Service-Key: Bearer <INTERNAL_SERVICE_KEY>.",
                        "name": "Authorization",
                        "in": "header",
                        "required": false
                    }
                ],
                "responses": {
                    "200": {
                        "description": "OK",
                        "schema": {
                            "type": "array",
                            "items": {
                                "$ref": "#/definitions/ForecastResult"
                            }
                        }
                    },
                    "401": {
                        "description": "Unauthorized",
                        "schema": {
                            "$ref": "#/definitions/ErrorResponse"
                        }
                    },
                    "500": {
                        "description": "Internal Server Error",
                        "schema": {
                            "$ref": "#/definitions/ErrorResponse"
                        }
                    }
                }
            },
            "post": {
                "summary": "Bulk save forecast results and finalize latest (internal service)",
                "description": "Compatibility endpoint for older two-step forecast-service flow. Replaces forecast_results for one run_id. Field results is required and must not be empty. After results are committed, a successful run is marked latest in the same transaction.",
                "tags": [
                    "Forecast Core"
                ],
                "consumes": [
                    "application/json"
                ],
                "produces": [
                    "application/json"
                ],
                "parameters": [
                    {
                        "type": "string",
                        "description": "Internal forecast service key. Backend also accepts Authorization: Bearer <INTERNAL_SERVICE_KEY>.",
                        "name": "X-Service-Key",
                        "in": "header",
                        "required": true
                    },
                    {
                        "type": "string",
                        "description": "Optional alternative to X-Service-Key: Bearer <INTERNAL_SERVICE_KEY>.",
                        "name": "Authorization",
                        "in": "header",
                        "required": false
                    },
                    {
                        "name": "body",
                        "in": "body",
                        "required": true,
                        "schema": {
                            "$ref": "#/definitions/ForecastResultsBulkRequest"
                        }
                    }
                ],
                "responses": {
                    "201": {
                        "description": "Created",
                        "schema": {
                            "$ref": "#/definitions/ForecastResultsBulkResponse"
                        }
                    },
                    "400": {
                        "description": "Bad Request",
                        "schema": {
                            "$ref": "#/definitions/ErrorResponse"
                        }
                    },
                    "401": {
                        "description": "Unauthorized",
                        "schema": {
                            "$ref": "#/definitions/ErrorResponse"
                        }
                    },
                    "403": {
                        "description": "Forbidden",
                        "schema": {
                            "$ref": "#/definitions/ErrorResponse"
                        }
                    },
                    "404": {
                        "description": "Not Found",
                        "schema": {
                            "$ref": "#/definitions/ErrorResponse"
                        }
                    },
                    "500": {
                        "description": "Internal Server Error",
                        "schema": {
                            "$ref": "#/definitions/ErrorResponse"
                        }
                    }
                }
            }
        },
        "/internal/forecast/forecast-results/{id}": {
            "get": {
                "summary": "Get forecast result by ID",
                "description": "Mengambil satu forecast result berdasarkan ID.",
                "tags": [
                    "Forecast Core"
                ],
                "produces": [
                    "application/json"
                ],
                "parameters": [
                    {
                        "type": "string",
                        "description": "Internal forecast service key. Backend also accepts Authorization: Bearer <INTERNAL_SERVICE_KEY>.",
                        "name": "X-Service-Key",
                        "in": "header",
                        "required": true
                    },
                    {
                        "type": "string",
                        "description": "Optional alternative to X-Service-Key: Bearer <INTERNAL_SERVICE_KEY>.",
                        "name": "Authorization",
                        "in": "header",
                        "required": false
                    },
                    {
                        "name": "id",
                        "in": "path",
                        "required": true,
                        "type": "integer",
                        "format": "int64"
                    }
                ],
                "responses": {
                    "200": {
                        "description": "OK",
                        "schema": {
                            "$ref": "#/definitions/ForecastResult"
                        }
                    },
                    "400": {
                        "description": "Bad Request",
                        "schema": {
                            "$ref": "#/definitions/ErrorResponse"
                        }
                    },
                    "401": {
                        "description": "Unauthorized",
                        "schema": {
                            "$ref": "#/definitions/ErrorResponse"
                        }
                    },
                    "404": {
                        "description": "Not Found",
                        "schema": {
                            "$ref": "#/definitions/ErrorResponse"
                        }
                    },
                    "500": {
                        "description": "Internal Server Error",
                        "schema": {
                            "$ref": "#/definitions/ErrorResponse"
                        }
                    }
                }
            }
        }
    },
    "definitions": {
        "ErrorResponse": {
            "type": "object",
            "properties": {
                "error": {
                    "type": "string"
                }
            }
        },
        "ForecastRunInput": {
            "type": "object",
            "required": [
                "store_id",
                "forecast_type",
                "horizon_label",
                "horizon_days",
                "granularity",
                "model_name",
                "model_version",
                "train_start_date",
                "train_end_date",
                "predict_start_date",
                "predict_end_date",
                "status"
            ],
            "properties": {
                "store_id": {
                    "type": "string",
                    "format": "uuid"
                },
                "forecast_type": {
                    "type": "string",
                    "enum": [
                        "visitors",
                        "sales",
                        "inventory"
                    ]
                },
                "horizon_label": {
                    "type": "string",
                    "enum": [
                        "daily",
                        "weekly",
                        "monthly"
                    ]
                },
                "horizon_days": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 366
                },
                "granularity": {
                    "type": "string",
                    "enum": [
                        "daily",
                        "weekly",
                        "monthly"
                    ]
                },
                "model_name": {
                    "type": "string"
                },
                "model_version": {
                    "type": "string"
                },
                "feature_version": {
                    "type": "string"
                },
                "train_start_date": {
                    "type": "string",
                    "format": "date"
                },
                "train_end_date": {
                    "type": "string",
                    "format": "date"
                },
                "predict_start_date": {
                    "type": "string",
                    "format": "date"
                },
                "predict_end_date": {
                    "type": "string",
                    "format": "date"
                },
                "metrics": {
                    "type": "string",
                    "description": "Valid JSON string. Empty value is normalized to {}."
                },
                "summary": {
                    "type": "string",
                    "description": "Valid JSON string. Empty value is normalized to {}."
                },
                "data_quality": {
                    "type": "string",
                    "description": "Valid JSON string. Empty value is normalized to {}."
                },
                "status": {
                    "type": "string",
                    "enum": [
                        "running",
                        "success",
                        "failed"
                    ]
                },
                "started_at": {
                    "type": "string",
                    "format": "date-time"
                },
                "finished_at": {
                    "type": "string",
                    "format": "date-time"
                },
                "error_message": {
                    "type": "string"
                }
            }
        },
        "ForecastRunCreateResponse": {
            "type": "object",
            "properties": {
                "run_id": {
                    "type": "integer",
                    "format": "int64"
                },
                "status": {
                    "type": "string"
                },
                "is_latest": {
                    "type": "boolean",
                    "description": "Always false on create-only endpoint. Latest is finalized after results are saved."
                },
                "message": {
                    "type": "string"
                }
            }
        },
        "ForecastRun": {
            "type": "object",
            "properties": {
                "id": {
                    "type": "integer",
                    "format": "int64"
                },
                "store_id": {
                    "type": "string",
                    "format": "uuid"
                },
                "forecast_type": {
                    "type": "string"
                },
                "horizon_label": {
                    "type": "string"
                },
                "horizon_days": {
                    "type": "integer"
                },
                "granularity": {
                    "type": "string"
                },
                "model_name": {
                    "type": "string"
                },
                "model_version": {
                    "type": "string"
                },
                "feature_version": {
                    "type": "string"
                },
                "train_start_date": {
                    "type": "string",
                    "format": "date"
                },
                "train_end_date": {
                    "type": "string",
                    "format": "date"
                },
                "predict_start_date": {
                    "type": "string",
                    "format": "date"
                },
                "predict_end_date": {
                    "type": "string",
                    "format": "date"
                },
                "metrics": {
                    "type": "object"
                },
                "summary": {
                    "type": "object"
                },
                "data_quality": {
                    "type": "object"
                },
                "status": {
                    "type": "string"
                },
                "is_latest": {
                    "type": "boolean"
                },
                "error_message": {
                    "type": "string"
                },
                "created_at": {
                    "type": "string",
                    "format": "date-time"
                },
                "started_at": {
                    "type": "string",
                    "format": "date-time"
                },
                "finished_at": {
                    "type": "string",
                    "format": "date-time"
                }
            }
        },
        "ForecastResultInput": {
            "type": "object",
            "required": [
                "target_date",
                "predicted_value"
            ],
            "properties": {
                "target_date": {
                    "type": "string",
                    "format": "date"
                },
                "predicted_value": {
                    "type": "number",
                    "format": "double",
                    "minimum": 0
                },
                "lower_bound": {
                    "type": "number",
                    "format": "double"
                },
                "upper_bound": {
                    "type": "number",
                    "format": "double"
                },
                "confidence_level": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 100
                },
                "actual_value": {
                    "type": "number",
                    "format": "double"
                },
                "item_id": {
                    "type": "string"
                },
                "item_type": {
                    "type": "string"
                }
            }
        },
        "ForecastResult": {
            "type": "object",
            "properties": {
                "id": {
                    "type": "integer",
                    "format": "int64"
                },
                "run_id": {
                    "type": "integer",
                    "format": "int64"
                },
                "target_date": {
                    "type": "string",
                    "format": "date"
                },
                "predicted_value": {
                    "type": "number",
                    "format": "double"
                },
                "lower_bound": {
                    "type": "number",
                    "format": "double"
                },
                "upper_bound": {
                    "type": "number",
                    "format": "double"
                },
                "confidence_level": {
                    "type": "integer"
                },
                "actual_value": {
                    "type": "number",
                    "format": "double"
                },
                "item_id": {
                    "type": "string"
                },
                "item_type": {
                    "type": "string"
                },
                "created_at": {
                    "type": "string",
                    "format": "date-time"
                }
            }
        },
        "ForecastResultsBulkRequest": {
            "type": "object",
            "required": [
                "run_id",
                "results"
            ],
            "properties": {
                "run_id": {
                    "type": "integer",
                    "format": "int64"
                },
                "results": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 1000,
                    "items": {
                        "$ref": "#/definitions/ForecastResultInput"
                    }
                }
            }
        },
        "ForecastResultsBulkResponse": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string"
                },
                "message": {
                    "type": "string"
                },
                "run_id": {
                    "type": "integer",
                    "format": "int64"
                },
                "count": {
                    "type": "integer"
                }
            }
        },
        "ForecastLatestResponse": {
            "type": "object",
            "properties": {
                "run": {
                    "$ref": "#/definitions/ForecastRun"
                },
                "results": {
                    "type": "array",
                    "items": {
                        "$ref": "#/definitions/ForecastResult"
                    }
                }
            }
        },
        "VisitorsDailyHistoryRow": {
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "format": "date"
                },
                "visitors": {
                    "type": "integer"
                },
                "valid_orders_count": {
                    "type": "integer"
                },
                "physical_orders_count": {
                    "type": "integer"
                },
                "online_orders_count": {
                    "type": "integer"
                },
                "dine_in_orders_count": {
                    "type": "integer"
                },
                "takeaway_orders_count": {
                    "type": "integer"
                },
                "physical_item_qty": {
                    "type": "number"
                },
                "avg_physical_item_qty": {
                    "type": "number"
                }
            }
        },
        "ForecastSaveInput": {
            "type": "object",
            "required": [
                "run",
                "results"
            ],
            "properties": {
                "run": {
                    "$ref": "#/definitions/ForecastRunInput"
                },
                "results": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 1000,
                    "items": {
                        "$ref": "#/definitions/ForecastResultInput"
                    }
                }
            }
        },
        "ForecastSaveResponse": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string"
                },
                "message": {
                    "type": "string"
                },
                "run_id": {
                    "type": "integer",
                    "format": "int64"
                },
                "count": {
                    "type": "integer"
                }
            }
        }
    }
}`

var SwaggerInfo = &swag.Spec{
	Version:          "1.3",
	Host:             "localhost:8080",
	BasePath:         "/",
	Schemes:          []string{"http"},
	Title:            "Sora Finance Forecast API",
	Description:      "Forecast-only API documentation. Forecast source of truth: forecast_runs + forecast_results. Forecast write endpoints are internal-service only. Latest forecast is only exposed after a successful run has saved at least one forecast_result.",
	InfoInstanceName: "swagger",
	SwaggerTemplate:  docTemplate,
}

func init() {
	swag.Register(SwaggerInfo.InstanceName(), SwaggerInfo)
}
