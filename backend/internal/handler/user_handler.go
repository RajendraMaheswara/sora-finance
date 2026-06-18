package handler

import (
	"net/http"
	"sora-finance-api/internal/auth"
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
	claims, ok := auth.ClaimsFromContext(r.Context())
	if !ok {
		respondWithJSON(w, http.StatusUnauthorized, map[string]string{"error": "unauthorized"})
		return
	}

	if auth.IsMember(claims) {
		respondWithJSON(w, http.StatusForbidden, map[string]string{"error": "forbidden: members cannot access users"})
		return
	}

	users, err := h.service.GetAll(r.Context())
	if err != nil {
		respondWithJSON(w, http.StatusInternalServerError, map[string]string{"error": err.Error()})
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
		respondWithJSON(w, http.StatusBadRequest, map[string]string{"error": err.Error()})
		return
	}
	if user == nil {
		respondWithJSON(w, http.StatusNotFound, map[string]string{"error": "not found"})
		return
	}
	user.Password = ""
	respondWithJSON(w, http.StatusOK, user)
}
