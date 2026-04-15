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

func (r *UserRepository) Create(ctx context.Context, u *models.User) error {
	query := `
		INSERT INTO m_users (
			m_store_id, m_role_access_id, m_role_id, m_user_verification_type_id,
			address, avatar_url, city_of_birth, date_of_birth, email, email_verified_at,
			is_active, is_email_verified, is_phone_verified, name, nip, password,
			phone, phone_verified_at, username, created_by
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20)
		RETURNING id, created_at
	`
	return r.db.QueryRow(ctx, query,
		u.StoreID, u.RoleAccessID, u.RoleID, u.UserVerificationTypeID,
		u.Address, u.AvatarURL, u.CityOfBirth, u.DateOfBirth, u.Email, u.EmailVerifiedAt,
		u.IsActive, u.IsEmailVerified, u.IsPhoneVerified, u.Name, u.NIP, u.Password,
		u.Phone, u.PhoneVerifiedAt, u.Username, u.CreatedBy,
	).Scan(&u.ID, &u.CreatedAt)
}

func (r *UserRepository) Update(ctx context.Context, u *models.User) error {
	query := `
		UPDATE m_users SET
			m_store_id = $1,
			m_role_access_id = $2,
			m_role_id = $3,
			m_user_verification_type_id = $4,
			address = $5,
			avatar_url = $6,
			city_of_birth = $7,
			date_of_birth = $8,
			email = $9,
			email_verified_at = $10,
			is_active = $11,
			is_email_verified = $12,
			is_phone_verified = $13,
			name = $14,
			nip = $15,
			password = $16,
			phone = $17,
			phone_verified_at = $18,
			username = $19,
			updated_at = NOW(),
			updated_by = $20
		WHERE id = $21 AND deleted_at IS NULL
	`
	cmdTag, err := r.db.Exec(ctx, query,
		u.StoreID, u.RoleAccessID, u.RoleID, u.UserVerificationTypeID,
		u.Address, u.AvatarURL, u.CityOfBirth, u.DateOfBirth, u.Email, u.EmailVerifiedAt,
		u.IsActive, u.IsEmailVerified, u.IsPhoneVerified, u.Name, u.NIP, u.Password,
		u.Phone, u.PhoneVerifiedAt, u.Username,
		u.UpdatedBy, u.ID,
	)
	if err != nil {
		return err
	}
	if cmdTag.RowsAffected() == 0 {
		return errors.New("user not found or already deleted")
	}
	return nil
}

func (r *UserRepository) Delete(ctx context.Context, id uuid.UUID, deletedBy uuid.UUID) error {
	query := `
		UPDATE m_users
		SET deleted_at = NOW(), deleted_by = $1
		WHERE id = $2 AND deleted_at IS NULL
	`
	cmdTag, err := r.db.Exec(ctx, query, deletedBy, id)
	if err != nil {
		return err
	}
	if cmdTag.RowsAffected() == 0 {
		return errors.New("user not found or already deleted")
	}
	return nil
}