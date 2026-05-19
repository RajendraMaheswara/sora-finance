package handler

import (
	"net/http"
	"sora-finance-api/internal/service"

	"github.com/go-chi/chi/v5"
)

type MenuIngredientHandler struct {
	service *service.MenuIngredientService
}

func NewMenuIngredientHandler(service *service.MenuIngredientService) *MenuIngredientHandler {
	return &MenuIngredientHandler{service: service}
}

// GetAll godoc
// @Summary      Get all menu ingredients
// @Description  Mengembalikan daftar semua menu ingredients
// @Tags         MenuIngredients
// @Produce      json
// @Success      200  {array}  models.MenuIngredient
// @Failure      500  {object}  map[string]interface{}
// @Router       /menu-ingredients [get]
func (h *MenuIngredientHandler) GetAll(w http.ResponseWriter, r *http.Request) {
	items, err := h.service.GetAll(r.Context())
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	respondWithJSON(w, http.StatusOK, items)
}

// GetByID godoc
// @Summary      Get menu ingredient by ID
// @Description  Mengembalikan satu menu ingredient berdasarkan ID
// @Tags         MenuIngredients
// @Produce      json
// @Param        id   path      string  true  "UUID"
// @Success      200  {object}  models.MenuIngredient
// @Failure      400  {object}  map[string]interface{}
// @Failure      404  {object}  map[string]interface{}
// @Router       /menu-ingredients/{id} [get]
func (h *MenuIngredientHandler) GetByID(w http.ResponseWriter, r *http.Request) {
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
