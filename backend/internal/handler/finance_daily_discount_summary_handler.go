package handler

import (
	"net/http"
	"sora-finance-api/internal/service"

	"github.com/go-chi/chi/v5"
)

type FinanceDailyDiscountSummaryHandler struct {
	service *service.FinanceDailyDiscountSummaryService
}

func NewFinanceDailyDiscountSummaryHandler(service *service.FinanceDailyDiscountSummaryService) *FinanceDailyDiscountSummaryHandler {
	return &FinanceDailyDiscountSummaryHandler{service: service}
}

// GetAll godoc
// @Summary      Get all finance daily discount summaries
// @Description  Mengembalikan daftar semua finance daily discount summaries
// @Tags         FinanceDailyDiscountSummaries
// @Produce      json
// @Success      200  {array}  models.FinanceDailyDiscountSummary
// @Failure      500  {object}  map[string]interface{}
// @Router       /finance-daily-discount-summaries [get]
func (h *FinanceDailyDiscountSummaryHandler) GetAll(w http.ResponseWriter, r *http.Request) {
	items, err := h.service.GetAll(r.Context())
	if err != nil {
		respondWithJSON(w, http.StatusInternalServerError, map[string]string{"error": err.Error()})
		return
	}
	respondWithJSON(w, http.StatusOK, items)
}

// GetByID godoc
// @Summary      Get finance daily discount summary by ID
// @Description  Mengembalikan satu finance daily discount summary berdasarkan ID
// @Tags         FinanceDailyDiscountSummaries
// @Produce      json
// @Param        id   path      string  true  "UUID"
// @Success      200  {object}  models.FinanceDailyDiscountSummary
// @Failure      400  {object}  map[string]interface{}
// @Failure      404  {object}  map[string]interface{}
// @Router       /finance-daily-discount-summaries/{id} [get]
func (h *FinanceDailyDiscountSummaryHandler) GetByID(w http.ResponseWriter, r *http.Request) {
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
