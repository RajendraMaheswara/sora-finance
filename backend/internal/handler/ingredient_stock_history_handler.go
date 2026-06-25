package handler

import (
	"net/http"
	"sora-finance-api/internal/service"

	"github.com/go-chi/chi/v5"
)

type IngredientStockHistoryHandler struct {
	service *service.IngredientStockHistoryService
}

func NewIngredientStockHistoryHandler(service *service.IngredientStockHistoryService) *IngredientStockHistoryHandler {
	return &IngredientStockHistoryHandler{service: service}
}

// GetAll godoc
// @Summary      Get all ingredient stock histories
// @Description  Mengembalikan daftar semua ingredient stock histories
// @Tags         IngredientStockHistories
// @Produce      json
// @Success      200  {array}  models.IngredientStockHistory
// @Failure      500  {object}  map[string]interface{}
// @Router       /ingredient-stock-histories [get]
func (h *IngredientStockHistoryHandler) GetAll(w http.ResponseWriter, r *http.Request) {
	items, err := h.service.GetAll(r.Context())
	if err != nil {
		respondWithJSON(w, http.StatusInternalServerError, map[string]string{"error": "internal server error"})
		return
	}
	respondWithJSON(w, http.StatusOK, items)
}

// GetByID godoc
// @Summary      Get ingredient stock history by ID
// @Description  Mengembalikan satu ingredient stock history berdasarkan ID
// @Tags         IngredientStockHistories
// @Produce      json
// @Param        id   path      string  true  "UUID"
// @Success      200  {object}  models.IngredientStockHistory
// @Failure      400  {object}  map[string]interface{}
// @Failure      404  {object}  map[string]interface{}
// @Router       /ingredient-stock-histories/{id} [get]
func (h *IngredientStockHistoryHandler) GetByID(w http.ResponseWriter, r *http.Request) {
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
