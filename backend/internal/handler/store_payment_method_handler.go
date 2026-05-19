package handler

import (
	"net/http"
	"sora-finance-api/internal/service"

	"github.com/go-chi/chi/v5"
)

type StorePaymentMethodHandler struct {
	service *service.StorePaymentMethodService
}

func NewStorePaymentMethodHandler(service *service.StorePaymentMethodService) *StorePaymentMethodHandler {
	return &StorePaymentMethodHandler{service: service}
}

// GetAll godoc
// @Summary      Get all store payment methods
// @Description  Mengembalikan daftar semua store payment methods
// @Tags         StorePaymentMethods
// @Produce      json
// @Success      200  {array}  models.StorePaymentMethod
// @Failure      500  {object}  map[string]interface{}
// @Router       /store-payment-methods [get]
func (h *StorePaymentMethodHandler) GetAll(w http.ResponseWriter, r *http.Request) {
	items, err := h.service.GetAll(r.Context())
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	respondWithJSON(w, http.StatusOK, items)
}

// GetByID godoc
// @Summary      Get store payment method by ID
// @Description  Mengembalikan satu store payment method berdasarkan ID
// @Tags         StorePaymentMethods
// @Produce      json
// @Param        id   path      string  true  "UUID"
// @Success      200  {object}  models.StorePaymentMethod
// @Failure      400  {object}  map[string]interface{}
// @Failure      404  {object}  map[string]interface{}
// @Router       /store-payment-methods/{id} [get]
func (h *StorePaymentMethodHandler) GetByID(w http.ResponseWriter, r *http.Request) {
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
