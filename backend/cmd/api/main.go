package main

import (
	"bytes"
	"context"
	"encoding/json"
	"io"
	"log"
	"net/http"
	"os"

	"sora-finance-api/internal/handler"
	"sora-finance-api/internal/repository"
	"sora-finance-api/internal/service"
	"sora-finance-api/pkg/db"

	"github.com/go-chi/chi/v5"
	"github.com/go-chi/chi/v5/middleware"
	"github.com/joho/godotenv"

	_ "sora-finance-api/docs"

	httpSwagger "github.com/swaggo/http-swagger"
)

// @title           Sora Finance API
// @version         1.0
// @description     REST API untuk aplikasi keuangan Sora (hanya GET endpoints)
// @termsOfService  http://swagger.io/terms/
// @contact.name    API Support
// @contact.url     http://www.swagger.io/support
// @contact.email   support@swagger.io
// @license.name    Apache 2.0
// @license.url     http://www.apache.org/licenses/LICENSE-2.0.html
// @host            localhost:8080
// @BasePath        /api
// @schemes         http

func main() {
	// Load .env
	if err := godotenv.Load(); err != nil {
		log.Println("No .env file found, using system env")
	}

	// Koneksi DB
	ctx := context.Background()
	pool, err := db.NewPostgresPool(ctx)
	if err != nil {
		log.Fatalf("Failed to connect to database: %v", err)
	}
	defer pool.Close()
	log.Println("Database connected")

	storeRepo := repository.NewStoreRepository(pool)
	storeService := service.NewStoreService(storeRepo)
	storeHandler := handler.NewStoreHandler(storeService)

	userRepo := repository.NewUserRepository(pool)
	userService := service.NewUserService(userRepo)
	userHandler := handler.NewUserHandler(userService)

	customerRepo := repository.NewCustomerRepository(pool)
	customerService := service.NewCustomerService(customerRepo)
	customerHandler := handler.NewCustomerHandler(customerService)

	testRepo := repository.NewTestTableRepository(pool)
	testService := service.NewTestTableService(testRepo)
	testHandler := handler.NewTestTableHandler(testService)

	foodIngredientRepo := repository.NewFoodIngredientRepository(pool)
	foodIngredientService := service.NewFoodIngredientService(foodIngredientRepo)
	foodIngredientHandler := handler.NewFoodIngredientHandler(foodIngredientService)

	menuIngredientRepo := repository.NewMenuIngredientRepository(pool)
	menuIngredientService := service.NewMenuIngredientService(menuIngredientRepo)
	menuIngredientHandler := handler.NewMenuIngredientHandler(menuIngredientService)

	menuOfferDetailRepo := repository.NewMenuOfferDetailRepository(pool)
	menuOfferDetailService := service.NewMenuOfferDetailService(menuOfferDetailRepo)
	menuOfferDetailHandler := handler.NewMenuOfferDetailHandler(menuOfferDetailService)

	menuOfferRepo := repository.NewMenuOfferRepository(pool)
	menuOfferService := service.NewMenuOfferService(menuOfferRepo)
	menuOfferHandler := handler.NewMenuOfferHandler(menuOfferService)

	menuOnlineOrderRepo := repository.NewMenuOnlineOrderRepository(pool)
	menuOnlineOrderService := service.NewMenuOnlineOrderService(menuOnlineOrderRepo)
	menuOnlineOrderHandler := handler.NewMenuOnlineOrderHandler(menuOnlineOrderService)

	menuPackagingIngredientRepo := repository.NewMenuPackagingIngredientRepository(pool)
	menuPackagingIngredientService := service.NewMenuPackagingIngredientService(menuPackagingIngredientRepo)
	menuPackagingIngredientHandler := handler.NewMenuPackagingIngredientHandler(menuPackagingIngredientService)

	menuPackagingRepo := repository.NewMenuPackagingRepository(pool)
	menuPackagingService := service.NewMenuPackagingService(menuPackagingRepo)
	menuPackagingHandler := handler.NewMenuPackagingHandler(menuPackagingService)

	menuVariantIngredientRepo := repository.NewMenuVariantIngredientRepository(pool)
	menuVariantIngredientService := service.NewMenuVariantIngredientService(menuVariantIngredientRepo)
	menuVariantIngredientHandler := handler.NewMenuVariantIngredientHandler(menuVariantIngredientService)

	menuVariantRepo := repository.NewMenuVariantRepository(pool)
	menuVariantService := service.NewMenuVariantService(menuVariantRepo)
	menuVariantHandler := handler.NewMenuVariantHandler(menuVariantService)

	menuRepo := repository.NewMenuRepository(pool)
	menuService := service.NewMenuService(menuRepo)
	menuHandler := handler.NewMenuHandler(menuService)

	paymentMethodRepo := repository.NewPaymentMethodRepository(pool)
	paymentMethodService := service.NewPaymentMethodService(paymentMethodRepo)
	paymentMethodHandler := handler.NewPaymentMethodHandler(paymentMethodService)

	storeDiscountRepo := repository.NewStoreDiscountRepository(pool)
	storeDiscountService := service.NewStoreDiscountService(storeDiscountRepo)
	storeDiscountHandler := handler.NewStoreDiscountHandler(storeDiscountService)

	storeOperationalHourRepo := repository.NewStoreOperationalHourRepository(pool)
	storeOperationalHourService := service.NewStoreOperationalHourService(storeOperationalHourRepo)
	storeOperationalHourHandler := handler.NewStoreOperationalHourHandler(storeOperationalHourService)

	storePaymentMethodRepo := repository.NewStorePaymentMethodRepository(pool)
	storePaymentMethodService := service.NewStorePaymentMethodService(storePaymentMethodRepo)
	storePaymentMethodHandler := handler.NewStorePaymentMethodHandler(storePaymentMethodService)

	subscriptionTypeRepo := repository.NewSubscriptionTypeRepository(pool)
	subscriptionTypeService := service.NewSubscriptionTypeService(subscriptionTypeRepo)
	subscriptionTypeHandler := handler.NewSubscriptionTypeHandler(subscriptionTypeService)

	financeDailyDiscountSummaryRepo := repository.NewFinanceDailyDiscountSummaryRepository(pool)
	financeDailyDiscountSummaryService := service.NewFinanceDailyDiscountSummaryService(financeDailyDiscountSummaryRepo)
	financeDailyDiscountSummaryHandler := handler.NewFinanceDailyDiscountSummaryHandler(financeDailyDiscountSummaryService)

	financeDailyHppSummaryRepo := repository.NewFinanceDailyHppSummaryRepository(pool)
	financeDailyHppSummaryService := service.NewFinanceDailyHppSummaryService(financeDailyHppSummaryRepo)
	financeDailyHppSummaryHandler := handler.NewFinanceDailyHppSummaryHandler(financeDailyHppSummaryService)

	financeDailyRegulationSummaryRepo := repository.NewFinanceDailyRegulationSummaryRepository(pool)
	financeDailyRegulationSummaryService := service.NewFinanceDailyRegulationSummaryService(financeDailyRegulationSummaryRepo)
	financeDailyRegulationSummaryHandler := handler.NewFinanceDailyRegulationSummaryHandler(financeDailyRegulationSummaryService)

	financeDailySummaryRepo := repository.NewFinanceDailySummaryRepository(pool)
	financeDailySummaryService := service.NewFinanceDailySummaryService(financeDailySummaryRepo)
	financeDailySummaryHandler := handler.NewFinanceDailySummaryHandler(financeDailySummaryService)

	financeMonthlySummaryRepo := repository.NewFinanceMonthlySummaryRepository(pool)
	financeMonthlySummaryService := service.NewFinanceMonthlySummaryService(financeMonthlySummaryRepo)
	financeMonthlySummaryHandler := handler.NewFinanceMonthlySummaryHandler(financeMonthlySummaryService)

	ingredientStockHistoryRepo := repository.NewIngredientStockHistoryRepository(pool)
	ingredientStockHistoryService := service.NewIngredientStockHistoryService(ingredientStockHistoryRepo)
	ingredientStockHistoryHandler := handler.NewIngredientStockHistoryHandler(ingredientStockHistoryService)

	orderItemRepo := repository.NewOrderItemRepository(pool)
	orderItemService := service.NewOrderItemService(orderItemRepo)
	orderItemHandler := handler.NewOrderItemHandler(orderItemService)

	orderRepo := repository.NewOrderRepository(pool)
	orderService := service.NewOrderService(orderRepo)
	orderHandler := handler.NewOrderHandler(orderService)

	salesDailySummaryRepo := repository.NewSalesDailySummaryRepository(pool)
	salesDailySummaryService := service.NewSalesDailySummaryService(salesDailySummaryRepo)
	salesDailySummaryHandler := handler.NewSalesDailySummaryHandler(salesDailySummaryService)

	salesMenuSummaryRepo := repository.NewSalesMenuSummaryRepository(pool)
	salesMenuSummaryService := service.NewSalesMenuSummaryService(salesMenuSummaryRepo)
	salesMenuSummaryHandler := handler.NewSalesMenuSummaryHandler(salesMenuSummaryService)

	salesMonthlySummaryRepo := repository.NewSalesMonthlySummaryRepository(pool)
	salesMonthlySummaryService := service.NewSalesMonthlySummaryService(salesMonthlySummaryRepo)
	salesMonthlySummaryHandler := handler.NewSalesMonthlySummaryHandler(salesMonthlySummaryService)

	// Router
	r := chi.NewRouter()
	r.Use(middleware.Logger)
	r.Use(middleware.Recoverer)

	// Fix CORS
	r.Use(func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			w.Header().Set("Access-Control-Allow-Origin", "*")
			w.Header().Set("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
			w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization")
			if r.Method == "OPTIONS" {
				w.WriteHeader(http.StatusOK)
				return
			}
			next.ServeHTTP(w, r)
		})
	})

	r.Get("/swagger/*", httpSwagger.Handler(
		httpSwagger.URL("http://localhost:8080/swagger/doc.json"),
	))

	r.Route("/api/stores", func(r chi.Router) {
		r.Get("/", storeHandler.GetAll)
		r.Get("/{id}", storeHandler.GetByID)
	})

	r.Route("/api/users", func(r chi.Router) {
		r.Get("/", userHandler.GetAll)
		r.Get("/{id}", userHandler.GetByID)
	})

	r.Route("/api/customers", func(r chi.Router) {
		r.Get("/", customerHandler.GetAll)
		r.Get("/{id}", customerHandler.GetByID)
	})

	r.Route("/api/test-table", func(r chi.Router) {
		r.Get("/", testHandler.GetAll)
		r.Get("/{id}", testHandler.GetByID)
	})

	// --- RUTE TEST JEMBATAN GOLANG KE PYTHON ---
	r.Get("/api/test-bridge", func(w http.ResponseWriter, req *http.Request) {
		// 1. Siapkan data dummy yang mau dikirim ke Python
		dataKePython := map[string]interface{}{
			"pesan":          "Halo Python, aku Golang! Tolong proses data ini.",
			"data_penjualan": []int{500, 600, 700, 800},
		}

		// Ubah data menjadi format JSON
		jsonData, _ := json.Marshal(dataKePython)

		// 2. Tembak/Kirim HTTP POST ke server Python
		resp, err := http.Post("http://127.0.0.1:5000/api/predict", "application/json", bytes.NewBuffer(jsonData))
		if err != nil {
			http.Error(w, "Gagal menghubungi Python: "+err.Error(), http.StatusInternalServerError)
			return
		}
		defer resp.Body.Close()

		// 3. Baca balasan/hasil ramalan dari Python
		balasanDariPython, _ := io.ReadAll(resp.Body)

		// 4. Teruskan balasan tersebut ke Browser/Flutter
		w.Header().Set("Content-Type", "application/json")
		w.Write(balasanDariPython)
	})
	// -------------------------------------------

	r.Route("/api/food-ingredients", func(r chi.Router) {
		r.Get("/", foodIngredientHandler.GetAll)
		r.Get("/{id}", foodIngredientHandler.GetByID)
	})

	r.Route("/api/menu-ingredients", func(r chi.Router) {
		r.Get("/", menuIngredientHandler.GetAll)
		r.Get("/{id}", menuIngredientHandler.GetByID)
	})

	r.Route("/api/menu-offer-details", func(r chi.Router) {
		r.Get("/", menuOfferDetailHandler.GetAll)
		r.Get("/{id}", menuOfferDetailHandler.GetByID)
	})

	r.Route("/api/menu-offers", func(r chi.Router) {
		r.Get("/", menuOfferHandler.GetAll)
		r.Get("/{id}", menuOfferHandler.GetByID)
	})

	r.Route("/api/menu-online-orders", func(r chi.Router) {
		r.Get("/", menuOnlineOrderHandler.GetAll)
		r.Get("/{id}", menuOnlineOrderHandler.GetByID)
	})

	r.Route("/api/menu-packaging-ingredients", func(r chi.Router) {
		r.Get("/", menuPackagingIngredientHandler.GetAll)
		r.Get("/{id}", menuPackagingIngredientHandler.GetByID)
	})

	r.Route("/api/menu-packagings", func(r chi.Router) {
		r.Get("/", menuPackagingHandler.GetAll)
		r.Get("/{id}", menuPackagingHandler.GetByID)
	})

	r.Route("/api/menu-variant-ingredients", func(r chi.Router) {
		r.Get("/", menuVariantIngredientHandler.GetAll)
		r.Get("/{id}", menuVariantIngredientHandler.GetByID)
	})

	r.Route("/api/menu-variants", func(r chi.Router) {
		r.Get("/", menuVariantHandler.GetAll)
		r.Get("/{id}", menuVariantHandler.GetByID)
	})

	r.Route("/api/menus", func(r chi.Router) {
		r.Get("/", menuHandler.GetAll)
		r.Get("/{id}", menuHandler.GetByID)
	})

	r.Route("/api/payment-methods", func(r chi.Router) {
		r.Get("/", paymentMethodHandler.GetAll)
		r.Get("/{id}", paymentMethodHandler.GetByID)
	})

	r.Route("/api/store-discounts", func(r chi.Router) {
		r.Get("/", storeDiscountHandler.GetAll)
		r.Get("/{id}", storeDiscountHandler.GetByID)
	})

	r.Route("/api/store-operational-hours", func(r chi.Router) {
		r.Get("/", storeOperationalHourHandler.GetAll)
		r.Get("/{id}", storeOperationalHourHandler.GetByID)
	})

	r.Route("/api/store-payment-methods", func(r chi.Router) {
		r.Get("/", storePaymentMethodHandler.GetAll)
		r.Get("/{id}", storePaymentMethodHandler.GetByID)
	})

	r.Route("/api/subscription-types", func(r chi.Router) {
		r.Get("/", subscriptionTypeHandler.GetAll)
		r.Get("/{id}", subscriptionTypeHandler.GetByID)
	})

	r.Route("/api/finance-daily-discount-summaries", func(r chi.Router) {
		r.Get("/", financeDailyDiscountSummaryHandler.GetAll)
		r.Get("/{id}", financeDailyDiscountSummaryHandler.GetByID)
	})

	r.Route("/api/finance-daily-hpp-summaries", func(r chi.Router) {
		r.Get("/", financeDailyHppSummaryHandler.GetAll)
		r.Get("/{id}", financeDailyHppSummaryHandler.GetByID)
	})

	r.Route("/api/finance-daily-regulation-summaries", func(r chi.Router) {
		r.Get("/", financeDailyRegulationSummaryHandler.GetAll)
		r.Get("/{id}", financeDailyRegulationSummaryHandler.GetByID)
	})

	r.Route("/api/finance-daily-summaries", func(r chi.Router) {
		r.Get("/", financeDailySummaryHandler.GetAll)
		r.Get("/{id}", financeDailySummaryHandler.GetByID)
	})

	r.Route("/api/finance-monthly-summaries", func(r chi.Router) {
		r.Get("/", financeMonthlySummaryHandler.GetAll)
		r.Get("/{id}", financeMonthlySummaryHandler.GetByID)
	})

	r.Route("/api/ingredient-stock-histories", func(r chi.Router) {
		r.Get("/", ingredientStockHistoryHandler.GetAll)
		r.Get("/{id}", ingredientStockHistoryHandler.GetByID)
	})

	r.Route("/api/order-items", func(r chi.Router) {
		r.Get("/", orderItemHandler.GetAll)
		r.Get("/{id}", orderItemHandler.GetByID)
	})

	r.Route("/api/orders", func(r chi.Router) {
		r.Get("/", orderHandler.GetAll)
		r.Get("/{id}", orderHandler.GetByID)
	})

	r.Route("/api/sales-daily-summaries", func(r chi.Router) {
		r.Get("/", salesDailySummaryHandler.GetAll)
		r.Get("/{id}", salesDailySummaryHandler.GetByID)
	})

	r.Route("/api/sales-menu-summaries", func(r chi.Router) {
		r.Get("/", salesMenuSummaryHandler.GetAll)
		r.Get("/{id}", salesMenuSummaryHandler.GetByID)
	})

	r.Route("/api/sales-monthly-summaries", func(r chi.Router) {
		r.Get("/", salesMonthlySummaryHandler.GetAll)
		r.Get("/{id}", salesMonthlySummaryHandler.GetByID)
	})

	port := os.Getenv("SERVER_PORT")
	if port == "" {
		port = "8080"
	}

	log.Printf("Server starting on :%s", port)
	if err := http.ListenAndServe(":"+port, r); err != nil {
		log.Fatal(err)
	}
}
