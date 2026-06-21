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
// @Description  Mengembalikan daftar semua sales daily summaries
// @Tags         SalesDailySummaries
// @Produce      json
// @Success      200  {array}  models.SalesDailySummary
// @Failure      500  {object}  map[string]interface{}
// @Router       /sales-daily-summaries [get]
func (h *SalesDailySummaryHandler) GetAll(w http.ResponseWriter, r *http.Request) {
	items, err := h.service.GetAll(r.Context())
	if err != nil {
		respondWithJSON(w, http.StatusInternalServerError, map[string]string{"error": err.Error()})
		return
	}
	respondWithJSON(w, http.StatusOK, items)
}

// GetByID godoc
// @Summary      Get sales daily summary by ID
// @Description  Mengembalikan satu sales daily summary berdasarkan ID
// @Tags         SalesDailySummaries
// @Produce      json
// @Param        id   path      string  true  "UUID"
// @Success      200  {object}  models.SalesDailySummary
// @Failure      400  {object}  map[string]interface{}
// @Failure      404  {object}  map[string]interface{}
// @Router       /sales-daily-summaries/{id} [get]
func (h *SalesDailySummaryHandler) GetByID(w http.ResponseWriter, r *http.Request) {
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
