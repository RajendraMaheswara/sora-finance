package main

import (
	"context"
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

	// Init repository, service, handler
	salesDailyRepo := repository.NewSalesDailySummaryRepository(pool)
	salesDailyService := service.NewSalesDailySummaryService(salesDailyRepo)
	salesDailyHandler := handler.NewSalesDailySummaryHandler(salesDailyService)

	repo := repository.NewMonthlySummaryRepository(pool)
	svc := service.NewMonthlySummaryService(repo)
	summaryHandler := handler.NewMonthlySummaryHandler(svc)

	storeRepo := repository.NewStoreRepository(pool)
	storeService := service.NewStoreService(storeRepo)
	storeHandler := handler.NewStoreHandler(storeService)

	userRepo := repository.NewUserRepository(pool)
	userService := service.NewUserService(userRepo)
	userHandler := handler.NewUserHandler(userService)

	customerRepo := repository.NewCustomerRepository(pool)
	customerService := service.NewCustomerService(customerRepo)
	customerHandler := handler.NewCustomerHandler(customerService)

	orderRepo := repository.NewOrderRepository(pool)
	orderService := service.NewOrderService(orderRepo)
	orderHandler := handler.NewOrderHandler(orderService)

	foodIngredientRepo := repository.NewFoodIngredientRepository(pool)
	foodIngredientService := service.NewFoodIngredientService(foodIngredientRepo)
	foodIngredientHandler := handler.NewFoodIngredientHandler(foodIngredientService)

	ingredientStockHistoryRepo := repository.NewIngredientStockHistoryRepository(pool)
	ingredientStockHistoryService := service.NewIngredientStockHistoryService(ingredientStockHistoryRepo)
	ingredientStockHistoryHandler := handler.NewIngredientStockHistoryHandler(ingredientStockHistoryService)

	// Router
	r := chi.NewRouter()
	r.Use(middleware.Logger)
	r.Use(middleware.Recoverer)

	r.Get("/swagger/*", httpSwagger.Handler(
		httpSwagger.URL("http://localhost:8080/swagger/doc.json"),
	))

	r.Route("/api/sales-daily-summaries", func(r chi.Router) {
		r.Get("/", salesDailyHandler.GetAll)
		r.Get("/{id}", salesDailyHandler.GetByID)
	})

	r.Route("/api/monthly-summaries", func(r chi.Router) {
		r.Get("/", summaryHandler.GetAll)
		r.Get("/{id}", summaryHandler.GetByID)
	})

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

	r.Route("/api/orders", func(r chi.Router) {
		r.Get("/", orderHandler.GetAll)
		r.Get("/{id}", orderHandler.GetByID)
	})

	r.Route("/api/food-ingredients", func(r chi.Router) {
		r.Get("/", foodIngredientHandler.GetAll)
		r.Get("/{id}", foodIngredientHandler.GetByID)
	})

	r.Route("/api/ingredient-stock-histories", func(r chi.Router) {
		r.Get("/", ingredientStockHistoryHandler.GetAll)
		r.Get("/{id}", ingredientStockHistoryHandler.GetByID)
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
