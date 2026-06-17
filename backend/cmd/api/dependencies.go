package main

import (
	"log"
	"os"

	authpkg "sora-finance-api/internal/auth"
	"sora-finance-api/internal/handler"
	"sora-finance-api/internal/repository"
	"sora-finance-api/internal/service"

	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/redis/go-redis/v9"
)

type AppDependencies struct {
	StoreHandler                         *handler.StoreHandler
	UserHandler                          *handler.UserHandler
	AuthHandler                          *handler.AuthHandler
	CustomerHandler                      *handler.CustomerHandler
	TestTableHandler                     *handler.TestTableHandler
	FoodIngredientHandler                *handler.FoodIngredientHandler
	MenuIngredientHandler                *handler.MenuIngredientHandler
	MenuOfferDetailHandler               *handler.MenuOfferDetailHandler
	MenuOfferHandler                     *handler.MenuOfferHandler
	MenuOnlineOrderHandler               *handler.MenuOnlineOrderHandler
	MenuPackagingIngredientHandler       *handler.MenuPackagingIngredientHandler
	MenuPackagingHandler                 *handler.MenuPackagingHandler
	MenuVariantIngredientHandler         *handler.MenuVariantIngredientHandler
	MenuVariantHandler                   *handler.MenuVariantHandler
	MenuHandler                          *handler.MenuHandler
	PaymentMethodHandler                 *handler.PaymentMethodHandler
	StoreDiscountHandler                 *handler.StoreDiscountHandler
	StoreOperationalHourHandler          *handler.StoreOperationalHourHandler
	StorePaymentMethodHandler            *handler.StorePaymentMethodHandler
	SubscriptionTypeHandler              *handler.SubscriptionTypeHandler
	FinanceDailyDiscountSummaryHandler   *handler.FinanceDailyDiscountSummaryHandler
	FinanceDailyHppSummaryHandler        *handler.FinanceDailyHppSummaryHandler
	FinanceDailyRegulationSummaryHandler *handler.FinanceDailyRegulationSummaryHandler
	FinanceDailySummaryHandler           *handler.FinanceDailySummaryHandler
	FinanceMonthlySummaryHandler         *handler.FinanceMonthlySummaryHandler
	ForecastPredictionHandler            *handler.ForecastPredictionHandler
	ForecastResultHandler                *handler.ForecastResultHandler
	ForecastRunHandler                   *handler.ForecastRunHandler
	IngredientStockHistoryHandler        *handler.IngredientStockHistoryHandler
	OrderItemHandler                     *handler.OrderItemHandler
	OrderHandler                         *handler.OrderHandler
	SalesDailySummaryHandler             *handler.SalesDailySummaryHandler
	SalesMenuSummaryHandler              *handler.SalesMenuSummaryHandler
	SalesMonthlySummaryHandler           *handler.SalesMonthlySummaryHandler
	JWTSecret                            string
}

func initDependencies(pool *pgxpool.Pool) *AppDependencies {
	storeRepo := repository.NewStoreRepository(pool)
	storeService := service.NewStoreService(storeRepo)
	storeHandler := handler.NewStoreHandler(storeService)

	userRepo := repository.NewUserRepository(pool)
	userService := service.NewUserService(userRepo)
	userHandler := handler.NewUserHandler(userService)

	jwtSecret := os.Getenv("JWT_SECRET")
	if jwtSecret == "" {
		log.Fatal("FATAL: JWT_SECRET environment variable is required")
	}

	redisURL := os.Getenv("REDIS_URL")
	if redisURL != "" {
		opt, err := redis.ParseURL(redisURL)
		if err != nil {
			log.Fatalf("FATAL: Failed to parse REDIS_URL: %v", err)
		}
		redisClient := redis.NewClient(opt)
		authpkg.InitRedis(redisClient)
		log.Println("Redis initialized for token blacklist")
	} else {
		log.Println("WARNING: REDIS_URL not set, token blacklist will not be persistent across restarts")
	}

	authService := service.NewAuthService(userRepo, jwtSecret)
	authHandler := handler.NewAuthHandler(authService)

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

	forecastPredictionRepo := repository.NewForecastPredictionRepository(pool)
	forecastPredictionService := service.NewForecastPredictionService(forecastPredictionRepo)
	forecastPredictionHandler := handler.NewForecastPredictionHandler(forecastPredictionService)

	forecastResultRepo := repository.NewForecastResultRepository(pool)
	forecastResultService := service.NewForecastResultService(forecastResultRepo)
	forecastResultHandler := handler.NewForecastResultHandler(forecastResultService)

	forecastRunRepo := repository.NewForecastRunRepository(pool)
	forecastRunService := service.NewForecastRunService(forecastRunRepo)
	forecastRunHandler := handler.NewForecastRunHandler(forecastRunService)

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

	return &AppDependencies{
		StoreHandler:                         storeHandler,
		UserHandler:                          userHandler,
		AuthHandler:                          authHandler,
		CustomerHandler:                      customerHandler,
		TestTableHandler:                     testHandler,
		FoodIngredientHandler:                foodIngredientHandler,
		MenuIngredientHandler:                menuIngredientHandler,
		MenuOfferDetailHandler:               menuOfferDetailHandler,
		MenuOfferHandler:                     menuOfferHandler,
		MenuOnlineOrderHandler:               menuOnlineOrderHandler,
		MenuPackagingIngredientHandler:       menuPackagingIngredientHandler,
		MenuPackagingHandler:                 menuPackagingHandler,
		MenuVariantIngredientHandler:         menuVariantIngredientHandler,
		MenuVariantHandler:                   menuVariantHandler,
		MenuHandler:                          menuHandler,
		PaymentMethodHandler:                 paymentMethodHandler,
		StoreDiscountHandler:                 storeDiscountHandler,
		StoreOperationalHourHandler:          storeOperationalHourHandler,
		StorePaymentMethodHandler:            storePaymentMethodHandler,
		SubscriptionTypeHandler:              subscriptionTypeHandler,
		FinanceDailyDiscountSummaryHandler:   financeDailyDiscountSummaryHandler,
		FinanceDailyHppSummaryHandler:        financeDailyHppSummaryHandler,
		FinanceDailyRegulationSummaryHandler: financeDailyRegulationSummaryHandler,
		FinanceDailySummaryHandler:           financeDailySummaryHandler,
		FinanceMonthlySummaryHandler:         financeMonthlySummaryHandler,
		ForecastPredictionHandler:            forecastPredictionHandler,
		ForecastResultHandler:                forecastResultHandler,
		ForecastRunHandler:                   forecastRunHandler,
		IngredientStockHistoryHandler:        ingredientStockHistoryHandler,
		OrderItemHandler:                     orderItemHandler,
		OrderHandler:                         orderHandler,
		SalesDailySummaryHandler:             salesDailySummaryHandler,
		SalesMenuSummaryHandler:              salesMenuSummaryHandler,
		SalesMonthlySummaryHandler:           salesMonthlySummaryHandler,
		JWTSecret:                            jwtSecret,
	}
}
