package handler

import (
	"net/http"
	"sora-finance-api/internal/service"

	"github.com/go-chi/chi/v5"
)

type FoodIngredientHandler struct {
	service *service.FoodIngredientService
}

func NewFoodIngredientHandler(service *service.FoodIngredientService) *FoodIngredientHandler {
	return &FoodIngredientHandler{service: service}
}

// GetAll godoc
// @Summary      Get all food ingredients
// @Description  Mengembalikan daftar semua bahan makanan
// @Tags         Food Ingredients
// @Produce      json
// @Success      200  {array}  models.FoodIngredient
// @Failure      500  {object}  map[string]interface{}
// @Router       /food-ingredients [get]
func (h *FoodIngredientHandler) GetAll(w http.ResponseWriter, r *http.Request) {
	ingredients, err := h.service.GetAll(r.Context())
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	respondWithJSON(w, http.StatusOK, ingredients)
}

// GetByID godoc
// @Summary      Get food ingredient by ID
// @Description  Mengembalikan satu bahan makanan berdasarkan ID
// @Tags         Food Ingredients
// @Produce      json
// @Param        id   path      string  true  "UUID"
// @Success      200  {object}  models.FoodIngredient
// @Failure      400  {object}  map[string]interface{}
// @Failure      404  {object}  map[string]interface{}
// @Router       /food-ingredients/{id} [get]
func (h *FoodIngredientHandler) GetByID(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	ingredient, err := h.service.GetByID(r.Context(), id)
	if err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}
	if ingredient == nil {
		http.Error(w, "not found", http.StatusNotFound)
		return
	}
	respondWithJSON(w, http.StatusOK, ingredient)
}
