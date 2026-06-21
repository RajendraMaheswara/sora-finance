package handler

import (
	"net/http"
	"sora-finance-api/internal/service"

	"github.com/go-chi/chi/v5"
)

type StoreDiscountHandler struct {
	service *service.StoreDiscountService
}

func NewStoreDiscountHandler(service *service.StoreDiscountService) *StoreDiscountHandler {
	return &StoreDiscountHandler{service: service}
}

// GetAll godoc
// @Summary      Get all store discounts
// @Description  Mengembalikan daftar semua store discounts
// @Tags         StoreDiscounts
// @Produce      json
// @Success      200  {array}  models.StoreDiscount
// @Failure      500  {object}  map[string]interface{}
// @Router       /store-discounts [get]
func (h *StoreDiscountHandler) GetAll(w http.ResponseWriter, r *http.Request) {
	items, err := h.service.GetAll(r.Context())
	if err != nil {
		respondWithJSON(w, http.StatusInternalServerError, map[string]string{"error": err.Error()})
		return
	}
	respondWithJSON(w, http.StatusOK, items)
}

// GetByID godoc
// @Summary      Get store discount by ID
// @Description  Mengembalikan satu store discount berdasarkan ID
// @Tags         StoreDiscounts
// @Produce      json
// @Param        id   path      string  true  "UUID"
// @Success      200  {object}  models.StoreDiscount
// @Failure      400  {object}  map[string]interface{}
// @Failure      404  {object}  map[string]interface{}
// @Router       /store-discounts/{id} [get]
func (h *StoreDiscountHandler) GetByID(w http.ResponseWriter, r *http.Request) {
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
