package main

import (
	"encoding/json"
	"net/http"
	"os"
	"strings"
	"time"

	authpkg "sora-finance-api/internal/auth"

	"github.com/go-chi/chi/v5"
	"github.com/go-chi/chi/v5/middleware"
	"github.com/go-chi/httprate"
	"github.com/jackc/pgx/v5/pgxpool"
	httpSwagger "github.com/swaggo/http-swagger"
)

func envBool(key string, defaultValue bool) bool {
	value := strings.ToLower(strings.TrimSpace(os.Getenv(key)))
	if value == "" {
		return defaultValue
	}
	return value == "1" || value == "true" || value == "yes" || value == "on"
}

type visitorsDailyHistoryRow struct {
	Date                string  `json:"date"`
	Visitors            int     `json:"visitors"`
	ValidOrdersCount    int     `json:"valid_orders_count"`
	PhysicalOrdersCount int     `json:"physical_orders_count"`
	OnlineOrdersCount   int     `json:"online_orders_count"`
	DineInOrdersCount   int     `json:"dine_in_orders_count"`
	TakeawayOrdersCount int     `json:"takeaway_orders_count"`
	PhysicalItemQty     float64 `json:"physical_item_qty"`
	AvgPhysicalItemQty  float64 `json:"avg_physical_item_qty"`
}

func handleInternalVisitorsDailyHistory(db *pgxpool.Pool) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		storeID := strings.TrimSpace(r.URL.Query().Get("store_id"))
		if storeID == "" {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusBadRequest)
			_ = json.NewEncoder(w).Encode(map[string]string{"error": "store_id is required"})
			return
		}

		rows, err := db.Query(r.Context(), `
			WITH order_item_totals AS (
				SELECT
					t_order_id,
					COALESCE(SUM(GREATEST(COALESCE(qty, 0), 0)), 0)::numeric(15,2) AS total_item_qty
				FROM t_order_items
				WHERE m_store_id = $1
				  AND deleted_at IS NULL
				GROUP BY t_order_id
			),
			valid_orders AS (
				SELECT
					DATE(o.created_at AT TIME ZONE 'Asia/Jakarta') AS date,
					o.id,
					o.m_table_id,
					o.m_menu_online_order_type_id,
					COALESCE(oit.total_item_qty, 0)::numeric(15,2) AS total_item_qty
				FROM t_orders o
				LEFT JOIN order_item_totals oit ON oit.t_order_id = o.id
				WHERE o.m_store_id = $2
				  AND o.deleted_at IS NULL
				  AND o.cancelled_at IS NULL
				  AND COALESCE(o.m_order_status_id, 0) <> 3
				  AND (o.m_order_status_id = 2 OR o.m_order_payment_status_id = 200)
			),
			order_estimates AS (
				SELECT
					*,
					CASE
						WHEN m_menu_online_order_type_id IS NOT NULL THEN 0
						WHEN total_item_qty <= 0 THEN 1
						WHEN total_item_qty <= 3 THEN 1
						WHEN total_item_qty <= 5 THEN 2
						WHEN total_item_qty <= 8 THEN 3
						ELSE 4
					END::integer AS estimated_visitors
				FROM valid_orders
			)
			SELECT
				date,
				COALESCE(SUM(estimated_visitors), 0)::integer AS visitors,
				COUNT(*)::integer AS valid_orders_count,
				COUNT(*) FILTER (WHERE m_menu_online_order_type_id IS NULL)::integer AS physical_orders_count,
				COUNT(*) FILTER (WHERE m_menu_online_order_type_id IS NOT NULL)::integer AS online_orders_count,
				COUNT(*) FILTER (
					WHERE m_menu_online_order_type_id IS NULL
					  AND m_table_id IS NOT NULL
				)::integer AS dine_in_orders_count,
				COUNT(*) FILTER (
					WHERE m_menu_online_order_type_id IS NULL
					  AND m_table_id IS NULL
				)::integer AS takeaway_orders_count,
				COALESCE(SUM(total_item_qty) FILTER (WHERE m_menu_online_order_type_id IS NULL), 0)::double precision AS physical_item_qty,
				COALESCE(AVG(total_item_qty) FILTER (WHERE m_menu_online_order_type_id IS NULL), 0)::double precision AS avg_physical_item_qty
			FROM order_estimates
			GROUP BY date
			ORDER BY date ASC
		`, storeID, storeID)
		if err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusInternalServerError)
			_ = json.NewEncoder(w).Encode(map[string]string{"error": "internal server error"})
			return
		}
		defer rows.Close()

		result := make([]visitorsDailyHistoryRow, 0)
		for rows.Next() {
			var row visitorsDailyHistoryRow
			var targetDate time.Time
			if err := rows.Scan(
				&targetDate,
				&row.Visitors,
				&row.ValidOrdersCount,
				&row.PhysicalOrdersCount,
				&row.OnlineOrdersCount,
				&row.DineInOrdersCount,
				&row.TakeawayOrdersCount,
				&row.PhysicalItemQty,
				&row.AvgPhysicalItemQty,
			); err != nil {
				w.Header().Set("Content-Type", "application/json")
				w.WriteHeader(http.StatusInternalServerError)
				_ = json.NewEncoder(w).Encode(map[string]string{"error": "internal server error"})
				return
			}
			row.Date = targetDate.Format("2006-01-02")
			result = append(result, row)
		}
		if err := rows.Err(); err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusInternalServerError)
			_ = json.NewEncoder(w).Encode(map[string]string{"error": "internal server error"})
			return
		}

		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		_ = json.NewEncoder(w).Encode(result)
	}
}

func setupRouter(deps *AppDependencies) *chi.Mux {
	r := chi.NewRouter()
	r.Use(middleware.Logger)
	r.Use(middleware.Recoverer)

	// Security & CORS Middleware
	allowedOriginsStr := os.Getenv("ALLOWED_ORIGINS")
	appEnv := strings.ToLower(strings.TrimSpace(os.Getenv("APP_ENV")))
	isProd := appEnv == "production" || appEnv == "prod"
	var allowedOrigins []string
	if allowedOriginsStr != "" {
		allowedOrigins = strings.Split(allowedOriginsStr, ",")
	}

	r.Use(func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			origin := r.Header.Get("Origin")
			allow := false

			if origin != "" {
				if len(allowedOrigins) == 0 && !isProd {
					allow = true
				} else {
					for _, o := range allowedOrigins {
						if strings.TrimSpace(o) == origin {
							allow = true
							break
						}
					}
				}
			}

			if allow {
				w.Header().Set("Access-Control-Allow-Origin", origin)
				w.Header().Set("Vary", "Origin")
			}

			w.Header().Set("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
			w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Service-Key")

			// Security Headers
			w.Header().Set("X-Content-Type-Options", "nosniff")
			w.Header().Set("X-Frame-Options", "DENY")
			w.Header().Set("X-XSS-Protection", "1; mode=block")
			w.Header().Set("Strict-Transport-Security", "max-age=31536000; includeSubDomains")

			if r.Method == "OPTIONS" {
				w.WriteHeader(http.StatusOK)
				return
			}
			next.ServeHTTP(w, r)
		})
	})

	// Health Check
	r.Get("/health", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{"status": "ok"}`))
	})

	if envBool("ENABLE_SWAGGER", !isProd) {
		r.Get("/swagger/*", httpSwagger.Handler(
			httpSwagger.URL("/swagger/doc.json"),
		))
	}

	r.Route("/api/auth", func(r chi.Router) {
		// Limit login to 5 requests per minute per IP
		r.With(httprate.LimitByIP(5, 1*time.Minute)).Post("/login", deps.AuthHandler.Login)
		r.Group(func(r chi.Router) {
			r.Use(authpkg.Middleware(deps.JWTSecret))
			r.Get("/me", deps.AuthHandler.Me)
			r.Post("/logout", deps.AuthHandler.Logout)
		})
	})

	// Internal forecast-service API.
	// This route is not for frontend/user traffic. It is protected by X-Service-Key
	// and injects system-admin claims to preserve the old forecast-service data behavior.
	r.Group(func(r chi.Router) {
		r.Use(authpkg.ServiceKeyMiddleware(os.Getenv("INTERNAL_SERVICE_KEY")))
		r.Use(authpkg.ForecastServiceClaimsMiddleware)

		r.Get("/internal/health", func(w http.ResponseWriter, r *http.Request) {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusOK)
			w.Write([]byte(`{"status":"ok","service":"forecast-internal"}`))
		})

		r.Route("/internal/forecast/stores", func(r chi.Router) {
			r.Get("/", deps.StoreHandler.GetAll)
			r.Get("/{id}", deps.StoreHandler.GetByID)
		})
		r.Route("/internal/forecast/orders", func(r chi.Router) {
			r.Get("/", deps.OrderHandler.GetAll)
			r.Get("/{id}", deps.OrderHandler.GetByID)
		})
		r.Get("/internal/forecast/visitors-daily-history", handleInternalVisitorsDailyHistory(deps.DB))
		r.Route("/internal/forecast/order-items", func(r chi.Router) {
			r.Get("/", deps.OrderItemHandler.GetAll)
			r.Get("/{id}", deps.OrderItemHandler.GetByID)
		})
		r.Route("/internal/forecast/store-operational-hours", func(r chi.Router) {
			r.Get("/", deps.StoreOperationalHourHandler.GetAll)
			r.Get("/{id}", deps.StoreOperationalHourHandler.GetByID)
		})
		r.Route("/internal/forecast/food-ingredients", func(r chi.Router) {
			r.Get("/", deps.FoodIngredientHandler.GetAll)
			r.Get("/{id}", deps.FoodIngredientHandler.GetByID)
		})
		r.Route("/internal/forecast/ingredient-stock-histories", func(r chi.Router) {
			r.Get("/", deps.IngredientStockHistoryHandler.GetAll)
			r.Get("/{id}", deps.IngredientStockHistoryHandler.GetByID)
		})
		r.Route("/internal/forecast/sales-daily-summaries", func(r chi.Router) {
			r.Get("/", deps.SalesDailySummaryHandler.GetAll)
			r.Get("/{id}", deps.SalesDailySummaryHandler.GetByID)
		})
		r.Route("/internal/forecast/sales-monthly-summaries", func(r chi.Router) {
			r.Get("/", deps.SalesMonthlySummaryHandler.GetAll)
			r.Get("/{id}", deps.SalesMonthlySummaryHandler.GetByID)
		})
		r.Post("/internal/forecast/save", deps.ForecastSaveHandler.Save)
		r.Route("/internal/forecast/forecast-runs", func(r chi.Router) {
			r.Get("/{id}", deps.ForecastRunHandler.GetByID)
			r.Post("/", deps.ForecastRunHandler.Create)
		})
		r.Route("/internal/forecast/forecast-results", func(r chi.Router) {
			r.Get("/", deps.ForecastResultHandler.GetAll)
			r.Get("/{id}", deps.ForecastResultHandler.GetByID)
			r.Post("/", deps.ForecastResultHandler.BulkCreate)
		})
	})

	r.Group(func(r chi.Router) {
		r.Use(authpkg.Middleware(deps.JWTSecret))
		r.Use(authpkg.StoreMiddleware)
		r.Get("/api/forecast/latest", deps.ForecastResultHandler.GetLatestForecast)

		r.Route("/api/stores", func(r chi.Router) {
			r.Get("/", deps.StoreHandler.GetAll)
			r.Get("/{id}", deps.StoreHandler.GetByID)
		})

		r.Route("/api/users", func(r chi.Router) {
			r.Get("/", deps.UserHandler.GetAll)
			r.Get("/{id}", deps.UserHandler.GetByID)
		})

		r.Route("/api/customers", func(r chi.Router) {
			r.Get("/", deps.CustomerHandler.GetAll)
			r.Get("/{id}", deps.CustomerHandler.GetByID)
		})

		if envBool("ENABLE_TEST_ROUTES", !isProd) {
			r.Route("/api/test-table", func(r chi.Router) {
				r.Get("/", deps.TestTableHandler.GetAll)
				r.Get("/{id}", deps.TestTableHandler.GetByID)
			})
		}

		r.Route("/api/food-ingredients", func(r chi.Router) {
			r.Get("/", deps.FoodIngredientHandler.GetAll)
			r.Get("/{id}", deps.FoodIngredientHandler.GetByID)
		})

		r.Route("/api/menu-ingredients", func(r chi.Router) {
			r.Get("/", deps.MenuIngredientHandler.GetAll)
			r.Get("/{id}", deps.MenuIngredientHandler.GetByID)
		})

		r.Route("/api/menu-offer-details", func(r chi.Router) {
			r.Get("/", deps.MenuOfferDetailHandler.GetAll)
			r.Get("/{id}", deps.MenuOfferDetailHandler.GetByID)
		})

		r.Route("/api/menu-offers", func(r chi.Router) {
			r.Get("/", deps.MenuOfferHandler.GetAll)
			r.Get("/{id}", deps.MenuOfferHandler.GetByID)
		})

		r.Route("/api/menu-online-orders", func(r chi.Router) {
			r.Get("/", deps.MenuOnlineOrderHandler.GetAll)
			r.Get("/{id}", deps.MenuOnlineOrderHandler.GetByID)
		})

		r.Route("/api/menu-packaging-ingredients", func(r chi.Router) {
			r.Get("/", deps.MenuPackagingIngredientHandler.GetAll)
			r.Get("/{id}", deps.MenuPackagingIngredientHandler.GetByID)
		})

		r.Route("/api/menu-packagings", func(r chi.Router) {
			r.Get("/", deps.MenuPackagingHandler.GetAll)
			r.Get("/{id}", deps.MenuPackagingHandler.GetByID)
		})

		r.Route("/api/menu-variant-ingredients", func(r chi.Router) {
			r.Get("/", deps.MenuVariantIngredientHandler.GetAll)
			r.Get("/{id}", deps.MenuVariantIngredientHandler.GetByID)
		})

		r.Route("/api/menu-variants", func(r chi.Router) {
			r.Get("/", deps.MenuVariantHandler.GetAll)
			r.Get("/{id}", deps.MenuVariantHandler.GetByID)
		})

		r.Route("/api/menus", func(r chi.Router) {
			r.Get("/", deps.MenuHandler.GetAll)
			r.Get("/{id}", deps.MenuHandler.GetByID)
		})

		r.Route("/api/store-discounts", func(r chi.Router) {
			r.Get("/", deps.StoreDiscountHandler.GetAll)
			r.Get("/{id}", deps.StoreDiscountHandler.GetByID)
		})

		r.Route("/api/store-operational-hours", func(r chi.Router) {
			r.Get("/", deps.StoreOperationalHourHandler.GetAll)
			r.Get("/{id}", deps.StoreOperationalHourHandler.GetByID)
		})

		r.Route("/api/finance-daily-discount-summaries", func(r chi.Router) {
			r.Get("/", deps.FinanceDailyDiscountSummaryHandler.GetAll)
			r.Get("/{id}", deps.FinanceDailyDiscountSummaryHandler.GetByID)
		})

		r.Route("/api/finance-daily-summaries", func(r chi.Router) {
			r.Get("/", deps.FinanceDailySummaryHandler.GetAll)
			r.Get("/{id}", deps.FinanceDailySummaryHandler.GetByID)
		})

		r.Get("/api/forecast/visitors/latest", deps.ForecastResultHandler.GetLatestVisitors)

		r.Route("/api/forecast-results", func(r chi.Router) {
			r.Get("/", deps.ForecastResultHandler.GetAll)
			r.Get("/{id}", deps.ForecastResultHandler.GetByID)
		})

		r.Route("/api/forecast-runs", func(r chi.Router) {
			r.Get("/{id}", deps.ForecastRunHandler.GetByID)
		})

		r.Route("/api/finance-monthly-summaries", func(r chi.Router) {
			r.Get("/", deps.FinanceMonthlySummaryHandler.GetAll)
			r.Get("/{id}", deps.FinanceMonthlySummaryHandler.GetByID)
		})

		r.Route("/api/ingredient-stock-histories", func(r chi.Router) {
			r.Get("/", deps.IngredientStockHistoryHandler.GetAll)
			r.Get("/{id}", deps.IngredientStockHistoryHandler.GetByID)
		})

		r.Route("/api/order-items", func(r chi.Router) {
			r.Get("/", deps.OrderItemHandler.GetAll)
			r.Get("/{id}", deps.OrderItemHandler.GetByID)
		})

		r.Route("/api/orders", func(r chi.Router) {
			r.Get("/", deps.OrderHandler.GetAll)
			r.Get("/{id}", deps.OrderHandler.GetByID)
		})

		r.Route("/api/sales-daily-summaries", func(r chi.Router) {
			r.Get("/", deps.SalesDailySummaryHandler.GetAll)
			r.Get("/{id}", deps.SalesDailySummaryHandler.GetByID)
		})

		r.Route("/api/sales-menu-summaries", func(r chi.Router) {
			r.Get("/", deps.SalesMenuSummaryHandler.GetAll)
			r.Get("/{id}", deps.SalesMenuSummaryHandler.GetByID)
		})

		r.Route("/api/sales-monthly-summaries", func(r chi.Router) {
			r.Get("/", deps.SalesMonthlySummaryHandler.GetAll)
			r.Get("/{id}", deps.SalesMonthlySummaryHandler.GetByID)
		})
	})

	return r
}
