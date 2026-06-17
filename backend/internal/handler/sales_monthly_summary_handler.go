package handler

import (
	"net/http"
	"sora-finance-api/internal/service"

	"github.com/go-chi/chi/v5"
)

type SalesMonthlySummaryHandler struct {
	service *service.SalesMonthlySummaryService
}

func NewSalesMonthlySummaryHandler(service *service.SalesMonthlySummaryService) *SalesMonthlySummaryHandler {
	return &SalesMonthlySummaryHandler{service: service}
}

// GetAll godoc
// @Summary      Get all sales monthly summaries
// @Description  Mengembalikan daftar semua sales monthly summaries
// @Tags         SalesMonthlySummaries
// @Produce      json
// @Success      200  {array}  models.SalesMonthlySummary
// @Failure      500  {object}  map[string]interface{}
// @Router       /sales-monthly-summaries [get]
func (h *SalesMonthlySummaryHandler) GetAll(w http.ResponseWriter, r *http.Request) {
	items, err := h.service.GetAll(r.Context())
	if err != nil {
		respondWithJSON(w, http.StatusInternalServerError, map[string]string{"error": err.Error()})
		return
	}
	respondWithJSON(w, http.StatusOK, items)
}

// GetByID godoc
// @Summary      Get sales monthly summary by ID
// @Description  Mengembalikan satu sales monthly summary berdasarkan ID
// @Tags         SalesMonthlySummaries
// @Produce      json
// @Param        id   path      string  true  "UUID"
// @Success      200  {object}  models.SalesMonthlySummary
// @Failure      400  {object}  map[string]interface{}
// @Failure      404  {object}  map[string]interface{}
// @Router       /sales-monthly-summaries/{id} [get]
func (h *SalesMonthlySummaryHandler) GetByID(w http.ResponseWriter, r *http.Request) {
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
