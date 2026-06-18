package main

import (
	"net/http"
	"os"
	"strings"
	"time"

	authpkg "sora-finance-api/internal/auth"

	"github.com/go-chi/chi/v5"
	"github.com/go-chi/chi/v5/middleware"
	"github.com/go-chi/httprate"
	httpSwagger "github.com/swaggo/http-swagger"
)

func envBool(key string, defaultValue bool) bool {
	value := strings.ToLower(strings.TrimSpace(os.Getenv(key)))
	if value == "" {
		return defaultValue
	}
	return value == "1" || value == "true" || value == "yes" || value == "on"
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

	r.Group(func(r chi.Router) {
		r.Use(authpkg.Middleware(deps.JWTSecret))
		r.Use(authpkg.StoreMiddleware)
		r.Get("/api/dashboard/forecast", deps.ForecastPredictionHandler.GetMyStoreForecast)

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

		r.Route("/api/payment-methods", func(r chi.Router) {
			r.Get("/", deps.PaymentMethodHandler.GetAll)
			r.Get("/{id}", deps.PaymentMethodHandler.GetByID)
		})

		r.Route("/api/store-discounts", func(r chi.Router) {
			r.Get("/", deps.StoreDiscountHandler.GetAll)
			r.Get("/{id}", deps.StoreDiscountHandler.GetByID)
		})

		r.Route("/api/store-operational-hours", func(r chi.Router) {
			r.Get("/", deps.StoreOperationalHourHandler.GetAll)
			r.Get("/{id}", deps.StoreOperationalHourHandler.GetByID)
		})

		r.Route("/api/store-payment-methods", func(r chi.Router) {
			r.Get("/", deps.StorePaymentMethodHandler.GetAll)
			r.Get("/{id}", deps.StorePaymentMethodHandler.GetByID)
		})

		r.Route("/api/subscription-types", func(r chi.Router) {
			r.Get("/", deps.SubscriptionTypeHandler.GetAll)
			r.Get("/{id}", deps.SubscriptionTypeHandler.GetByID)
		})

		r.Route("/api/finance-daily-discount-summaries", func(r chi.Router) {
			r.Get("/", deps.FinanceDailyDiscountSummaryHandler.GetAll)
			r.Get("/{id}", deps.FinanceDailyDiscountSummaryHandler.GetByID)
		})

		r.Route("/api/finance-daily-hpp-summaries", func(r chi.Router) {
			r.Get("/", deps.FinanceDailyHppSummaryHandler.GetAll)
			r.Get("/{id}", deps.FinanceDailyHppSummaryHandler.GetByID)
		})

		r.Route("/api/finance-daily-regulation-summaries", func(r chi.Router) {
			r.Get("/", deps.FinanceDailyRegulationSummaryHandler.GetAll)
			r.Get("/{id}", deps.FinanceDailyRegulationSummaryHandler.GetByID)
		})

		r.Route("/api/finance-daily-summaries", func(r chi.Router) {
			r.Get("/", deps.FinanceDailySummaryHandler.GetAll)
			r.Get("/{id}", deps.FinanceDailySummaryHandler.GetByID)
		})

		r.Route("/api/forecast-predictions", func(r chi.Router) {
			r.Get("/", deps.ForecastPredictionHandler.GetAll)
			r.Get("/{id}", deps.ForecastPredictionHandler.GetByID)
			r.Post("/", deps.ForecastPredictionHandler.Save)
		})

		r.Route("/api/forecast-results", func(r chi.Router) {
			r.Get("/", deps.ForecastResultHandler.GetAll)
			r.Get("/{id}", deps.ForecastResultHandler.GetByID)
			r.Post("/", deps.ForecastResultHandler.BulkCreate)
		})

		r.Route("/api/forecast-runs", func(r chi.Router) {
			r.Post("/", deps.ForecastRunHandler.Create)
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
