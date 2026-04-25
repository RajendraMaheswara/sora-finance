package handler

import (
	"net/http"
	"sora-finance-api/internal/service"

	"github.com/go-chi/chi/v5"
)

type UserHandler struct {
	service *service.UserService
}

func NewUserHandler(service *service.UserService) *UserHandler {
	return &UserHandler{service: service}
}

// GetAll godoc
// @Summary      Get all users
// @Description  Mengembalikan daftar semua user (password dihilangkan)
// @Tags         Users
// @Produce      json
// @Success      200  {array}  models.User
// @Failure      500  {object}  map[string]interface{}
// @Router       /users [get]
func (h *UserHandler) GetAll(w http.ResponseWriter, r *http.Request) {
	users, err := h.service.GetAll(r.Context())
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	// Hilangkan password dari response
	for i := range users {
		users[i].Password = ""
	}
	respondWithJSON(w, http.StatusOK, users)
}

// GetByID godoc
// @Summary      Get user by ID
// @Description  Mengembalikan satu user berdasarkan ID (password dihilangkan)
// @Tags         Users
// @Produce      json
// @Param        id   path      string  true  "UUID"
// @Success      200  {object}  models.User
// @Failure      400  {object}  map[string]interface{}
// @Failure      404  {object}  map[string]interface{}
// @Router       /users/{id} [get]
func (h *UserHandler) GetByID(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	user, err := h.service.GetByID(r.Context(), id)
	if err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}
	if user == nil {
		http.Error(w, "not found", http.StatusNotFound)
		return
	}
	user.Password = ""
	respondWithJSON(w, http.StatusOK, user)
}
