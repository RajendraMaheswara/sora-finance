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

	port := os.Getenv("SERVER_PORT")
	if port == "" {
		port = "8080"
	}

	log.Printf("Server starting on :%s", port)
	if err := http.ListenAndServe(":"+port, r); err != nil {
		log.Fatal(err)
	}
}
