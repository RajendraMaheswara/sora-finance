package handler

import (
	"net/http"
	"sora-finance-api/internal/service"

	"github.com/go-chi/chi/v5"
)

type MenuVariantIngredientHandler struct {
	service *service.MenuVariantIngredientService
}

func NewMenuVariantIngredientHandler(service *service.MenuVariantIngredientService) *MenuVariantIngredientHandler {
	return &MenuVariantIngredientHandler{service: service}
}

// GetAll godoc
// @Summary      Get all menu variant ingredients
// @Description  Mengembalikan daftar semua menu variant ingredients
// @Tags         MenuVariantIngredients
// @Produce      json
// @Success      200  {array}  models.MenuVariantIngredient
// @Failure      500  {object}  map[string]interface{}
// @Router       /menu-variant-ingredients [get]
func (h *MenuVariantIngredientHandler) GetAll(w http.ResponseWriter, r *http.Request) {
	items, err := h.service.GetAll(r.Context())
	if err != nil {
		respondWithJSON(w, http.StatusInternalServerError, map[string]string{"error": err.Error()})
		return
	}
	respondWithJSON(w, http.StatusOK, items)
}

// GetByID godoc
// @Summary      Get menu variant ingredient by ID
// @Description  Mengembalikan satu menu variant ingredient berdasarkan ID
// @Tags         MenuVariantIngredients
// @Produce      json
// @Param        id   path      string  true  "UUID"
// @Success      200  {object}  models.MenuVariantIngredient
// @Failure      400  {object}  map[string]interface{}
// @Failure      404  {object}  map[string]interface{}
// @Router       /menu-variant-ingredients/{id} [get]
func (h *MenuVariantIngredientHandler) GetByID(w http.ResponseWriter, r *http.Request) {
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
