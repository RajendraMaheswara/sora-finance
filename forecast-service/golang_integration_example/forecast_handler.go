// golang_integration_example/forecast_handler.go
// Contoh HTTP handler di Golang yang memanggil Python Forecast Service.
// Daftarkan route ini di main.go Anda.

package forecastclient

import (
	"encoding/json"
	"net/http"

	"github.com/go-chi/chi/v5"
)

type ForecastHandler struct {
	client *ForecastClient
}

func NewForecastHandler() *ForecastHandler {
	return &ForecastHandler{client: NewForecastClient()}
}

// RegisterRoutes mendaftarkan semua route forecast ke chi router.
//
// Tambahkan ini di main.go Anda:
//
//	forecastHandler := forecastclient.NewForecastHandler()
//	forecastHandler.RegisterRoutes(r)
func (h *ForecastHandler) RegisterRoutes(r chi.Router) {
	r.Route("/api/forecast", func(r chi.Router) {
		r.Get("/predict/{storeId}", h.GetForecast)
		r.Post("/retrain/{storeId}", h.RetrainModel)
		r.Get("/health", h.HealthCheck)
	})
}

// GetForecast godoc
// @Summary      Prediksi jumlah pengunjung
// @Description  Ambil prediksi jumlah pengunjung harian dari Python forecast service
// @Tags         Forecast
// @Produce      json
// @Param        storeId   path     string  true  "Store UUID"
// @Param        days      query    int     false "Jumlah hari (default: 30)"
// @Success      200       {object} ForecastResponse
// @Router       /api/forecast/predict/{storeId} [get]
func (h *ForecastHandler) GetForecast(w http.ResponseWriter, r *http.Request) {
	storeID := chi.URLParam(r, "storeId")

	daysStr := r.URL.Query().Get("days")
	days := 30
	if daysStr != "" {
		if _, err := json.Number(daysStr).Int64(); err == nil {
			if d, ok := parseInt(daysStr); ok && d > 0 && d <= 365 {
				days = d
			}
		}
	}

	result, err := h.client.GetForecast(r.Context(), storeID, days)
	if err != nil {
		http.Error(w, `{"status":"error","message":"`+err.Error()+`"}`, http.StatusBadGateway)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(result)
}

// RetrainModel godoc
// @Summary      Retrain model prediksi
// @Description  Minta Python service untuk melatih ulang model Random Forest
// @Tags         Forecast
// @Produce      json
// @Param        storeId  path  string  true  "Store UUID"
// @Success      200      {object} RetrainResponse
// @Router       /api/forecast/retrain/{storeId} [post]
func (h *ForecastHandler) RetrainModel(w http.ResponseWriter, r *http.Request) {
	storeID := chi.URLParam(r, "storeId")

	result, err := h.client.RetrainModel(r.Context(), storeID, true)
	if err != nil {
		http.Error(w, `{"status":"error","message":"`+err.Error()+`"}`, http.StatusBadGateway)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(result)
}

// HealthCheck godoc
// @Summary      Health check forecast service
// @Tags         Forecast
// @Produce      json
// @Success      200  {object}  HealthResponse
// @Router       /api/forecast/health [get]
func (h *ForecastHandler) HealthCheck(w http.ResponseWriter, r *http.Request) {
	result, err := h.client.HealthCheck(r.Context())
	if err != nil {
		http.Error(w, `{"status":"error","message":"Forecast service tidak bisa dijangkau"}`, http.StatusServiceUnavailable)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(result)
}

func parseInt(s string) (int, bool) {
	var n int
	for _, c := range s {
		if c < '0' || c > '9' {
			return 0, false
		}
		n = n*10 + int(c-'0')
	}
	return n, true
}
