package handler

import (
	"net/http"
	"sora-finance-api/internal/service"

	"github.com/go-chi/chi/v5"
)

type SalesDailySummaryHandler struct {
	service *service.SalesDailySummaryService
}

func NewSalesDailySummaryHandler(service *service.SalesDailySummaryService) *SalesDailySummaryHandler {
	return &SalesDailySummaryHandler{service: service}
}

// GetAll godoc
// @Summary      Get all sales daily summaries
// @Description  Mengembalikan daftar semua ringkasan penjualan harian
// @Tags         Sales Daily Summaries
// @Produce      json
// @Success      200  {array}  models.SalesDailySummary
// @Failure      500  {object}  map[string]interface{}
// @Router       /sales-daily-summaries [get]
func (h *SalesDailySummaryHandler) GetAll(w http.ResponseWriter, r *http.Request) {
	summaries, err := h.service.GetAll(r.Context())
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	respondWithJSON(w, http.StatusOK, summaries)
}

// GetByID godoc
// @Summary      Get sales daily summary by ID
// @Description  Mengembalikan satu ringkasan penjualan harian berdasarkan ID
// @Tags         Sales Daily Summaries
// @Produce      json
// @Param        id   path      string  true  "UUID"
// @Success      200  {object}  models.SalesDailySummary
// @Failure      400  {object}  map[string]interface{}
// @Failure      404  {object}  map[string]interface{}
// @Router       /sales-daily-summaries/{id} [get]
func (h *SalesDailySummaryHandler) GetByID(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	summary, err := h.service.GetByID(r.Context(), id)
	if err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}
	if summary == nil {
		http.Error(w, "not found", http.StatusNotFound)
		return
	}
	respondWithJSON(w, http.StatusOK, summary)
}
