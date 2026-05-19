package handler

import (
	"net/http"
	"sora-finance-api/internal/service"

	"github.com/go-chi/chi/v5"
)

type PaymentMethodHandler struct {
	service *service.PaymentMethodService
}

func NewPaymentMethodHandler(service *service.PaymentMethodService) *PaymentMethodHandler {
	return &PaymentMethodHandler{service: service}
}

// GetAll godoc
// @Summary      Get all payment methods
// @Description  Mengembalikan daftar semua payment methods
// @Tags         PaymentMethods
// @Produce      json
// @Success      200  {array}  models.PaymentMethod
// @Failure      500  {object}  map[string]interface{}
// @Router       /payment-methods [get]
func (h *PaymentMethodHandler) GetAll(w http.ResponseWriter, r *http.Request) {
	items, err := h.service.GetAll(r.Context())
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	respondWithJSON(w, http.StatusOK, items)
}

// GetByID godoc
// @Summary      Get payment method by ID
// @Description  Mengembalikan satu payment method berdasarkan ID
// @Tags         PaymentMethods
// @Produce      json
// @Param        id   path      string  true  "UUID"
// @Success      200  {object}  models.PaymentMethod
// @Failure      400  {object}  map[string]interface{}
// @Failure      404  {object}  map[string]interface{}
// @Router       /payment-methods/{id} [get]
func (h *PaymentMethodHandler) GetByID(w http.ResponseWriter, r *http.Request) {
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
