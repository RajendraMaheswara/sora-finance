package repository

import (
	"context"
	"errors"
	"sora-finance-api/internal/auth"
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
	claims, _ := auth.ClaimsFromContext(ctx)
	query := `
		SELECT id, m_store_id, m_role_access_id, m_role_id, m_user_verification_type_id,
		       address, avatar_url, city_of_birth, date_of_birth, email, email_verified_at,
		       is_active, is_email_verified, is_phone_verified, name, nip, password,
		       phone, phone_verified_at, username,
		       created_at, created_by, updated_at, updated_by, deleted_at, deleted_by
		FROM m_users
		WHERE deleted_at IS NULL
	`
	var args []interface{}
	if claims != nil && !auth.IsSystemAdmin(claims) {
		query += ` AND m_store_id = $1`
		args = append(args, claims.StoreID)
	}
	query += ` ORDER BY created_at DESC`

	rows, err := r.db.Query(ctx, query, args...)
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
	claims, _ := auth.ClaimsFromContext(ctx)
	query := `
		SELECT id, m_store_id, m_role_access_id, m_role_id, m_user_verification_type_id,
		       address, avatar_url, city_of_birth, date_of_birth, email, email_verified_at,
		       is_active, is_email_verified, is_phone_verified, name, nip, password,
		       phone, phone_verified_at, username,
		       created_at, created_by, updated_at, updated_by, deleted_at, deleted_by
		FROM m_users
		WHERE id = $1 AND deleted_at IS NULL
	`
	args := []interface{}{id}
	if claims != nil && !auth.IsSystemAdmin(claims) {
		query += ` AND m_store_id = $2`
		args = append(args, claims.StoreID)
	}

	err := r.db.QueryRow(ctx, query, args...).Scan(
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
func (r *UserRepository) FindByCredential(ctx context.Context, identifier, password string) (*models.AuthUser, error) {
	var u models.AuthUser
	err := r.db.QueryRow(ctx, `
		SELECT u.id, u.m_store_id, u.m_role_id, u.username, u.name, u.email, s.name AS store_name, r.name AS role_name
		FROM m_users u
		LEFT JOIN m_stores s ON s.id = u.m_store_id AND s.deleted_at IS NULL
		LEFT JOIN m_roles r ON r.id = u.m_role_id AND r.deleted_at IS NULL
		WHERE (LOWER(u.username) = LOWER($1) OR LOWER(COALESCE(u.email, '')) = LOWER($1))
		  AND u.password = extensions.crypt($2, u.password)
		  AND u.is_active = true
		  AND u.deleted_at IS NULL
		LIMIT 1
	`, identifier, password).Scan(
		&u.ID, &u.StoreID, &u.RoleID, &u.Username, &u.Name, &u.Email, &u.StoreName, &u.RoleName,
	)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, nil
		}
		return nil, err
	}
	return &u, nil
}
