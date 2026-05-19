package handler

import (
	"net/http"
	"sora-finance-api/internal/service"

	"github.com/go-chi/chi/v5"
)

type FinanceDailyRegulationSummaryHandler struct {
	service *service.FinanceDailyRegulationSummaryService
}

func NewFinanceDailyRegulationSummaryHandler(service *service.FinanceDailyRegulationSummaryService) *FinanceDailyRegulationSummaryHandler {
	return &FinanceDailyRegulationSummaryHandler{service: service}
}

// GetAll godoc
// @Summary      Get all finance daily regulation summaries
// @Description  Mengembalikan daftar semua finance daily regulation summaries
// @Tags         FinanceDailyRegulationSummaries
// @Produce      json
// @Success      200  {array}  models.FinanceDailyRegulationSummary
// @Failure      500  {object}  map[string]interface{}
// @Router       /finance-daily-regulation-summaries [get]
func (h *FinanceDailyRegulationSummaryHandler) GetAll(w http.ResponseWriter, r *http.Request) {
	items, err := h.service.GetAll(r.Context())
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	respondWithJSON(w, http.StatusOK, items)
}

// GetByID godoc
// @Summary      Get finance daily regulation summary by ID
// @Description  Mengembalikan satu finance daily regulation summary berdasarkan ID
// @Tags         FinanceDailyRegulationSummaries
// @Produce      json
// @Param        id   path      string  true  "UUID"
// @Success      200  {object}  models.FinanceDailyRegulationSummary
// @Failure      400  {object}  map[string]interface{}
// @Failure      404  {object}  map[string]interface{}
// @Router       /finance-daily-regulation-summaries/{id} [get]
func (h *FinanceDailyRegulationSummaryHandler) GetByID(w http.ResponseWriter, r *http.Request) {
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
