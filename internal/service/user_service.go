package service

import (
	"context"
	"errors"
	"sora-finance-api/internal/models"
	"sora-finance-api/internal/repository"

	"github.com/google/uuid"
)

type UserService struct {
	repo *repository.UserRepository
}

func NewUserService(repo *repository.UserRepository) *UserService {
	return &UserService{repo: repo}
}

// GetAll godoc
// @Summary      Get all users
// @Description  Mengembalikan daftar semua user (password dihilangkan)
// @Tags         Users
// @Produce      json
// @Success      200  {array}  models.User
// @Failure      500  {object}  map[string]interface{}
// @Router       /users [get]
func (s *UserService) GetAll(ctx context.Context) ([]models.User, error) {
	return s.repo.GetAll(ctx)
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
func (s *UserService) GetByID(ctx context.Context, id string) (*models.User, error) {
	uuidID, err := uuid.Parse(id)
	if err != nil {
		return nil, errors.New("invalid uuid format")
	}
	return s.repo.GetByID(ctx, uuidID)
}