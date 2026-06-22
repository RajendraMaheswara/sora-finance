package service

import (
	"context"
	"errors"
	"strings"
	"time"

	"sora-finance-api/internal/auth"
	"sora-finance-api/internal/models"
	"sora-finance-api/internal/repository"
)

type AuthService struct {
	userRepo  *repository.UserRepository
	jwtSecret string
}

func NewAuthService(userRepo *repository.UserRepository, jwtSecret string) *AuthService {
	return &AuthService{userRepo: userRepo, jwtSecret: jwtSecret}
}

func (s *AuthService) Login(ctx context.Context, req models.LoginRequest) (*models.LoginResponse, error) {
	identifier := strings.TrimSpace(req.Username)
	password := strings.TrimSpace(req.Password)
	if identifier == "" || password == "" {
		return nil, errors.New("username/email dan password wajib diisi")
	}

	user, err := s.userRepo.FindByCredential(ctx, identifier, password)
	if err != nil {
		return nil, err
	}
	if user == nil {
		return nil, errors.New("username/email atau password salah")
	}

	token, err := auth.GenerateToken(s.jwtSecret, user, 24*time.Hour)
	if err != nil {
		return nil, err
	}

	return &models.LoginResponse{Token: token, User: user}, nil
}
