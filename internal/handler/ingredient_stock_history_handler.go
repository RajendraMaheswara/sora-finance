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
// @Description  Mengembalikan daftar semua riwayat stok bahan
// @Tags         Ingredient Stock Histories
// @Produce      json
// @Success      200  {array}  models.IngredientStockHistory
// @Failure      500  {object}  map[string]interface{}
// @Router       /ingredient-stock-histories [get]
func (h *IngredientStockHistoryHandler) GetAll(w http.ResponseWriter, r *http.Request) {
	histories, err := h.service.GetAll(r.Context())
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	respondWithJSON(w, http.StatusOK, histories)
}

// GetByID godoc
// @Summary      Get ingredient stock history by ID
// @Description  Mengembalikan satu riwayat stok bahan berdasarkan ID
// @Tags         Ingredient Stock Histories
// @Produce      json
// @Param        id   path      string  true  "UUID"
// @Success      200  {object}  models.IngredientStockHistory
// @Failure      400  {object}  map[string]interface{}
// @Failure      404  {object}  map[string]interface{}
// @Router       /ingredient-stock-histories/{id} [get]
func (h *IngredientStockHistoryHandler) GetByID(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	history, err := h.service.GetByID(r.Context(), id)
	if err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}
	if history == nil {
		http.Error(w, "not found", http.StatusNotFound)
		return
	}
	respondWithJSON(w, http.StatusOK, history)
}
