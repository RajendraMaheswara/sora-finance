package handler

import (
	"net/http"
	"sora-finance-api/internal/service"

	"github.com/go-chi/chi/v5"
)

type CustomerHandler struct {
	service *service.CustomerService
}

func NewCustomerHandler(service *service.CustomerService) *CustomerHandler {
	return &CustomerHandler{service: service}
}

// GetAll godoc
// @Summary      Get all customers
// @Description  Mengembalikan daftar semua customer
// @Tags         Customers
// @Produce      json
// @Success      200  {array}  models.Customer
// @Failure      500  {object}  map[string]interface{}
// @Router       /customers [get]
func (h *CustomerHandler) GetAll(w http.ResponseWriter, r *http.Request) {
	customers, err := h.service.GetAll(r.Context())
	if err != nil {
		respondWithJSON(w, http.StatusInternalServerError, map[string]string{"error": "internal server error"})
		return
	}
	respondWithJSON(w, http.StatusOK, customers)
}

// GetByID godoc
// @Summary      Get customer by ID
// @Description  Mengembalikan satu customer berdasarkan ID
// @Tags         Customers
// @Produce      json
// @Param        id   path      string  true  "UUID"
// @Success      200  {object}  models.Customer
// @Failure      400  {object}  map[string]interface{}
// @Failure      404  {object}  map[string]interface{}
// @Router       /customers/{id} [get]
func (h *CustomerHandler) GetByID(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	customer, err := h.service.GetByID(r.Context(), id)
	if err != nil {
		respondWithJSON(w, http.StatusBadRequest, map[string]string{"error": err.Error()})
		return
	}
	if customer == nil {
		respondWithJSON(w, http.StatusNotFound, map[string]string{"error": "not found"})
		return
	}
	respondWithJSON(w, http.StatusOK, customer)
}
