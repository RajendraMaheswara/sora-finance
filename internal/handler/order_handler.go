package handler

import (
	"net/http"
	"sora-finance-api/internal/service"

	"github.com/go-chi/chi/v5"
)

type OrderHandler struct {
	service *service.OrderService
}

func NewOrderHandler(service *service.OrderService) *OrderHandler {
	return &OrderHandler{service: service}
}

// GetAll godoc
// @Summary      Get all orders
// @Description  Mengembalikan daftar semua order
// @Tags         Orders
// @Produce      json
// @Success      200  {array}  models.Order
// @Failure      500  {object}  map[string]interface{}
// @Router       /orders [get]
func (h *OrderHandler) GetAll(w http.ResponseWriter, r *http.Request) {
	orders, err := h.service.GetAll(r.Context())
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	respondWithJSON(w, http.StatusOK, orders)
}

// GetByID godoc
// @Summary      Get order by ID
// @Description  Mengembalikan satu order berdasarkan ID
// @Tags         Orders
// @Produce      json
// @Param        id   path      string  true  "UUID"
// @Success      200  {object}  models.Order
// @Failure      400  {object}  map[string]interface{}
// @Failure      404  {object}  map[string]interface{}
// @Router       /orders/{id} [get]
func (h *OrderHandler) GetByID(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	order, err := h.service.GetByID(r.Context(), id)
	if err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}
	if order == nil {
		http.Error(w, "not found", http.StatusNotFound)
		return
	}
	respondWithJSON(w, http.StatusOK, order)
}
