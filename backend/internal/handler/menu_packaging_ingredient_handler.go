package handler

import (
	"net/http"
	"sora-finance-api/internal/service"

	"github.com/go-chi/chi/v5"
)

type MenuPackagingIngredientHandler struct {
	service *service.MenuPackagingIngredientService
}

func NewMenuPackagingIngredientHandler(service *service.MenuPackagingIngredientService) *MenuPackagingIngredientHandler {
	return &MenuPackagingIngredientHandler{service: service}
}

// GetAll godoc
// @Summary      Get all menu packaging ingredients
// @Description  Mengembalikan daftar semua menu packaging ingredients
// @Tags         MenuPackagingIngredients
// @Produce      json
// @Success      200  {array}  models.MenuPackagingIngredient
// @Failure      500  {object}  map[string]interface{}
// @Router       /menu-packaging-ingredients [get]
func (h *MenuPackagingIngredientHandler) GetAll(w http.ResponseWriter, r *http.Request) {
	items, err := h.service.GetAll(r.Context())
	if err != nil {
		respondWithJSON(w, http.StatusInternalServerError, map[string]string{"error": err.Error()})
		return
	}
	respondWithJSON(w, http.StatusOK, items)
}

// GetByID godoc
// @Summary      Get menu packaging ingredient by ID
// @Description  Mengembalikan satu menu packaging ingredient berdasarkan ID
// @Tags         MenuPackagingIngredients
// @Produce      json
// @Param        id   path      string  true  "UUID"
// @Success      200  {object}  models.MenuPackagingIngredient
// @Failure      400  {object}  map[string]interface{}
// @Failure      404  {object}  map[string]interface{}
// @Router       /menu-packaging-ingredients/{id} [get]
func (h *MenuPackagingIngredientHandler) GetByID(w http.ResponseWriter, r *http.Request) {
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
