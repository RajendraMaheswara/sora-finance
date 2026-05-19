package handler

import (
	"net/http"
	"sora-finance-api/internal/service"

	"github.com/go-chi/chi/v5"
)

type FinanceMonthlySummaryHandler struct {
	service *service.FinanceMonthlySummaryService
}

func NewFinanceMonthlySummaryHandler(service *service.FinanceMonthlySummaryService) *FinanceMonthlySummaryHandler {
	return &FinanceMonthlySummaryHandler{service: service}
}

// GetAll godoc
// @Summary      Get all finance monthly summaries
// @Description  Mengembalikan daftar semua finance monthly summaries
// @Tags         FinanceMonthlySummaries
// @Produce      json
// @Success      200  {array}  models.FinanceMonthlySummary
// @Failure      500  {object}  map[string]interface{}
// @Router       /finance-monthly-summaries [get]
func (h *FinanceMonthlySummaryHandler) GetAll(w http.ResponseWriter, r *http.Request) {
	items, err := h.service.GetAll(r.Context())
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	respondWithJSON(w, http.StatusOK, items)
}

// GetByID godoc
// @Summary      Get finance monthly summary by ID
// @Description  Mengembalikan satu finance monthly summary berdasarkan ID
// @Tags         FinanceMonthlySummaries
// @Produce      json
// @Param        id   path      string  true  "UUID"
// @Success      200  {object}  models.FinanceMonthlySummary
// @Failure      400  {object}  map[string]interface{}
// @Failure      404  {object}  map[string]interface{}
// @Router       /finance-monthly-summaries/{id} [get]
func (h *FinanceMonthlySummaryHandler) GetByID(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	item, err := h.service.GetByID(r.Context(), id)
	if err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}
	if item == nil {
		http.Error(w, "not found", http.StatusNotFound)
		return
	}
	respondWithJSON(w, http.StatusOK, item)
}
