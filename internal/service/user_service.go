package service

import (
	"context"
	"errors"
	"sora-finance-api/internal/models"
	"sora-finance-api/internal/repository"

	"github.com/google/uuid"
	"golang.org/x/crypto/bcrypt"
)

type UserService struct {
	repo *repository.UserRepository
}

func NewUserService(repo *repository.UserRepository) *UserService {
	return &UserService{repo: repo}
}

func (s *UserService) GetAll(ctx context.Context) ([]models.User, error) {
	return s.repo.GetAll(ctx)
}

func (s *UserService) GetByID(ctx context.Context, id string) (*models.User, error) {
	uuidID, err := uuid.Parse(id)
	if err != nil {
		return nil, errors.New("invalid uuid format")
	}
	return s.repo.GetByID(ctx, uuidID)
}

func (s *UserService) Create(ctx context.Context, req *models.User) (*models.User, error) {
	// Validasi wajib
	if req.Name == "" {
		return nil, errors.New("name is required")
	}
	if req.Username == "" {
		return nil, errors.New("username is required")
	}
	if req.Password == "" {
		return nil, errors.New("password is required")
	}
	if req.CreatedBy == uuid.Nil {
		return nil, errors.New("created_by is required")
	}
	// Hash password
	hashed, err := bcrypt.GenerateFromPassword([]byte(req.Password), bcrypt.DefaultCost)
	if err != nil {
		return nil, errors.New("failed to hash password")
	}
	req.Password = string(hashed)

	// Set default values
	req.IsActive = false
	req.IsEmailVerified = false
	req.IsPhoneVerified = false

	err = s.repo.Create(ctx, req)
	if err != nil {
		return nil, err
	}
	// Hilangkan password dari response
	req.Password = ""
	return req, nil
}

func (s *UserService) Update(ctx context.Context, id string, req *models.User) error {
	uuidID, err := uuid.Parse(id)
	if err != nil {
		return errors.New("invalid uuid format")
	}
	existing, err := s.repo.GetByID(ctx, uuidID)
	if err != nil {
		return err
	}
	if existing == nil {
		return errors.New("user not found")
	}
	// Update field yang boleh diubah
	if req.StoreID != nil {
		existing.StoreID = req.StoreID
	}
	if req.RoleAccessID != nil {
		existing.RoleAccessID = req.RoleAccessID
	}
	if req.RoleID != nil {
		existing.RoleID = req.RoleID
	}
	if req.UserVerificationTypeID != nil {
		existing.UserVerificationTypeID = req.UserVerificationTypeID
	}
	if req.Address != nil {
		existing.Address = req.Address
	}
	if req.AvatarURL != nil {
		existing.AvatarURL = req.AvatarURL
	}
	if req.CityOfBirth != nil {
		existing.CityOfBirth = req.CityOfBirth
	}
	if req.DateOfBirth != nil {
		existing.DateOfBirth = req.DateOfBirth
	}
	if req.Email != nil {
		existing.Email = req.Email
	}
	if req.EmailVerifiedAt != nil {
		existing.EmailVerifiedAt = req.EmailVerifiedAt
	}
	if req.IsActive != existing.IsActive {
		existing.IsActive = req.IsActive
	}
	if req.IsEmailVerified != existing.IsEmailVerified {
		existing.IsEmailVerified = req.IsEmailVerified
	}
	if req.IsPhoneVerified != existing.IsPhoneVerified {
		existing.IsPhoneVerified = req.IsPhoneVerified
	}
	if req.Name != "" {
		existing.Name = req.Name
	}
	if req.NIP != nil {
		existing.NIP = req.NIP
	}
	if req.Password != "" {
		hashed, err := bcrypt.GenerateFromPassword([]byte(req.Password), bcrypt.DefaultCost)
		if err != nil {
			return errors.New("failed to hash password")
		}
		existing.Password = string(hashed)
	}
	if req.Phone != nil {
		existing.Phone = req.Phone
	}
	if req.PhoneVerifiedAt != nil {
		existing.PhoneVerifiedAt = req.PhoneVerifiedAt
	}
	if req.Username != "" {
		existing.Username = req.Username
	}
	existing.UpdatedBy = req.UpdatedBy

	return s.repo.Update(ctx, existing)
}

func (s *UserService) Delete(ctx context.Context, id string, deletedBy uuid.UUID) error {
	uuidID, err := uuid.Parse(id)
	if err != nil {
		return errors.New("invalid uuid format")
	}
	return s.repo.Delete(ctx, uuidID, deletedBy)
}