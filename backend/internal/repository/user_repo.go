package repository

import (
	"context"
	"errors"
	"sora-finance-api/internal/models"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

type UserRepository struct {
	db *pgxpool.Pool
}

func NewUserRepository(db *pgxpool.Pool) *UserRepository {
	return &UserRepository{db: db}
}

func (r *UserRepository) GetAll(ctx context.Context) ([]models.User, error) {
	rows, err := r.db.Query(ctx, `
		SELECT id, m_store_id, m_role_access_id, m_role_id, m_user_verification_type_id,
		       address, avatar_url, city_of_birth, date_of_birth, email, email_verified_at,
		       is_active, is_email_verified, is_phone_verified, name, nip, password,
		       phone, phone_verified_at, username,
		       created_at, created_by, updated_at, updated_by, deleted_at, deleted_by
		FROM m_users
		WHERE deleted_at IS NULL
		ORDER BY created_at DESC
	`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var users []models.User
	for rows.Next() {
		var u models.User
		err := rows.Scan(
			&u.ID, &u.StoreID, &u.RoleAccessID, &u.RoleID, &u.UserVerificationTypeID,
			&u.Address, &u.AvatarURL, &u.CityOfBirth, &u.DateOfBirth, &u.Email, &u.EmailVerifiedAt,
			&u.IsActive, &u.IsEmailVerified, &u.IsPhoneVerified, &u.Name, &u.NIP, &u.Password,
			&u.Phone, &u.PhoneVerifiedAt, &u.Username,
			&u.CreatedAt, &u.CreatedBy, &u.UpdatedAt, &u.UpdatedBy, &u.DeletedAt, &u.DeletedBy,
		)
		if err != nil {
			return nil, err
		}
		users = append(users, u)
	}
	return users, nil
}

func (r *UserRepository) GetByID(ctx context.Context, id uuid.UUID) (*models.User, error) {
	var u models.User
	err := r.db.QueryRow(ctx, `
		SELECT id, m_store_id, m_role_access_id, m_role_id, m_user_verification_type_id,
		       address, avatar_url, city_of_birth, date_of_birth, email, email_verified_at,
		       is_active, is_email_verified, is_phone_verified, name, nip, password,
		       phone, phone_verified_at, username,
		       created_at, created_by, updated_at, updated_by, deleted_at, deleted_by
		FROM m_users
		WHERE id = $1 AND deleted_at IS NULL
	`, id).Scan(
		&u.ID, &u.StoreID, &u.RoleAccessID, &u.RoleID, &u.UserVerificationTypeID,
		&u.Address, &u.AvatarURL, &u.CityOfBirth, &u.DateOfBirth, &u.Email, &u.EmailVerifiedAt,
		&u.IsActive, &u.IsEmailVerified, &u.IsPhoneVerified, &u.Name, &u.NIP, &u.Password,
		&u.Phone, &u.PhoneVerifiedAt, &u.Username,
		&u.CreatedAt, &u.CreatedBy, &u.UpdatedAt, &u.UpdatedBy, &u.DeletedAt, &u.DeletedBy,
	)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, nil
		}
		return nil, err
	}
	return &u, nil
}