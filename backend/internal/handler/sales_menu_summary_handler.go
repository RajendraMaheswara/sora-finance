package handler

import (
	"net/http"
	"sora-finance-api/internal/service"

	"github.com/go-chi/chi/v5"
)

type SalesMenuSummaryHandler struct {
	service *service.SalesMenuSummaryService
}

func NewSalesMenuSummaryHandler(service *service.SalesMenuSummaryService) *SalesMenuSummaryHandler {
	return &SalesMenuSummaryHandler{service: service}
}

// GetAll godoc
// @Summary      Get all sales menu summaries
// @Description  Mengembalikan daftar semua sales menu summaries
// @Tags         SalesMenuSummaries
// @Produce      json
// @Success      200  {array}  models.SalesMenuSummary
// @Failure      500  {object}  map[string]interface{}
// @Router       /sales-menu-summaries [get]
func (h *SalesMenuSummaryHandler) GetAll(w http.ResponseWriter, r *http.Request) {
	items, err := h.service.GetAll(r.Context())
	if err != nil {
		respondWithJSON(w, http.StatusInternalServerError, map[string]string{"error": "internal server error"})
		return
	}
	respondWithJSON(w, http.StatusOK, items)
}

// GetByID godoc
// @Summary      Get sales menu summary by ID
// @Description  Mengembalikan satu sales menu summary berdasarkan ID
// @Tags         SalesMenuSummaries
// @Produce      json
// @Param        id   path      string  true  "UUID"
// @Success      200  {object}  models.SalesMenuSummary
// @Failure      400  {object}  map[string]interface{}
// @Failure      404  {object}  map[string]interface{}
// @Router       /sales-menu-summaries/{id} [get]
func (h *SalesMenuSummaryHandler) GetByID(w http.ResponseWriter, r *http.Request) {
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
