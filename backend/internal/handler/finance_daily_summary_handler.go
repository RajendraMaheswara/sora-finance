package handler

import (
	"net/http"
	"sora-finance-api/internal/service"

	"github.com/go-chi/chi/v5"
)

type FinanceDailySummaryHandler struct {
	service *service.FinanceDailySummaryService
}

func NewFinanceDailySummaryHandler(service *service.FinanceDailySummaryService) *FinanceDailySummaryHandler {
	return &FinanceDailySummaryHandler{service: service}
}

// GetAll godoc
// @Summary      Get all finance daily summaries
// @Description  Mengembalikan daftar semua finance daily summaries
// @Tags         FinanceDailySummaries
// @Produce      json
// @Success      200  {array}  models.FinanceDailySummary
// @Failure      500  {object}  map[string]interface{}
// @Router       /finance-daily-summaries [get]
func (h *FinanceDailySummaryHandler) GetAll(w http.ResponseWriter, r *http.Request) {
	items, err := h.service.GetAll(r.Context())
	if err != nil {
		respondWithJSON(w, http.StatusInternalServerError, map[string]string{"error": err.Error()})
		return
	}
	respondWithJSON(w, http.StatusOK, items)
}

// GetByID godoc
// @Summary      Get finance daily summary by ID
// @Description  Mengembalikan satu finance daily summary berdasarkan ID
// @Tags         FinanceDailySummaries
// @Produce      json
// @Param        id   path      string  true  "UUID"
// @Success      200  {object}  models.FinanceDailySummary
// @Failure      400  {object}  map[string]interface{}
// @Failure      404  {object}  map[string]interface{}
// @Router       /finance-daily-summaries/{id} [get]
func (h *FinanceDailySummaryHandler) GetByID(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	item, err := h.service.GetByID(r.Context(), id)
	if err != nil {
		respondWithJSON(w, http.StatusBadRequest, map[string]string{"error": err.Error()})
		return
	}
	if item == nil {
		respondWithJSON(w, http.StatusNotFound, map[string]string{"error": "not found"})
		return
	}
	respondWithJSON(w, http.StatusOK, item)
}
