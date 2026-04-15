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
)

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
	repo := repository.NewMonthlySummaryRepository(pool)
	svc := service.NewMonthlySummaryService(repo)
	summaryHandler := handler.NewMonthlySummaryHandler(svc)

	storeRepo := repository.NewStoreRepository(pool)
	storeService := service.NewStoreService(storeRepo)
	storeHandler := handler.NewStoreHandler(storeService)

	userRepo := repository.NewUserRepository(pool)
	userService := service.NewUserService(userRepo)
	userHandler := handler.NewUserHandler(userService)

	// Router
	r := chi.NewRouter()
	r.Use(middleware.Logger)
	r.Use(middleware.Recoverer)

	r.Route("/api/monthly-summaries", func(r chi.Router) {
		r.Get("/", summaryHandler.GetAll)
		r.Post("/", summaryHandler.Create)
		r.Get("/{id}", summaryHandler.GetByID)
		r.Put("/{id}", summaryHandler.Update)
		r.Delete("/{id}", summaryHandler.Delete)
	})

	r.Route("/api/stores", func(r chi.Router) {
		r.Get("/", storeHandler.GetAll)
		r.Post("/", storeHandler.Create)
		r.Get("/{id}", storeHandler.GetByID)
		r.Put("/{id}", storeHandler.Update)
		r.Delete("/{id}", storeHandler.Delete)
	})

	r.Route("/api/users", func(r chi.Router) {
		r.Get("/", userHandler.GetAll)
		r.Post("/", userHandler.Create)
		r.Get("/{id}", userHandler.GetByID)
		r.Put("/{id}", userHandler.Update)
		r.Delete("/{id}", userHandler.Delete)
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