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

type StoreRepository struct {
	db *pgxpool.Pool
}

func NewStoreRepository(db *pgxpool.Pool) *StoreRepository {
	return &StoreRepository{db: db}
}

// GetAll mengambil daftar store. Admin dapat melihat semua store, sedangkan
// user non-admin hanya dapat melihat store yang sesuai dengan store_id JWT.
func (r *StoreRepository) GetAll(ctx context.Context, page, limit int) ([]models.Store, error) {
	if page < 1 {
		page = 1
	}
	if limit < 1 {
		limit = 100
	}
	if limit > 200 {
		limit = 200
	}
	offset := (page - 1) * limit

	claims, _ := auth.ClaimsFromContext(ctx)
	query := `
		SELECT id, m_subscription_type_id, coins, expired_date, is_active, name,
		       created_at, created_by, updated_at, updated_by, deleted_at, deleted_by,
		       is_tutorial_completed, tutorial_step
		FROM m_stores
		WHERE deleted_at IS NULL`
	args := []interface{}{}

	if claims != nil && !auth.IsSystemAdmin(claims) {
		query += ` AND id = $1`
		args = append(args, claims.StoreID)
	}

	args = append(args, limit, offset)
	limitArg := len(args) - 1
	offsetArg := len(args)
	query += `
		ORDER BY created_at DESC
		LIMIT ` + sqlParam(limitArg) + ` OFFSET ` + sqlParam(offsetArg)

	rows, err := r.db.Query(ctx, query, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var stores []models.Store
	for rows.Next() {
		var s models.Store
		err := rows.Scan(
			&s.ID, &s.SubscriptionTypeID, &s.Coins, &s.ExpiredDate, &s.IsActive, &s.Name,
			&s.CreatedAt, &s.CreatedBy, &s.UpdatedAt, &s.UpdatedBy, &s.DeletedAt, &s.DeletedBy,
			&s.IsTutorialCompleted, &s.TutorialStep,
		)
		if err != nil {
			return nil, err
		}
		stores = append(stores, s)
	}
	return stores, rows.Err()
}

// GetByID mengambil satu store berdasarkan UUID. User non-admin tidak dapat
// membaca store lain walaupun mengetahui UUID-nya.
func (r *StoreRepository) GetByID(ctx context.Context, id uuid.UUID) (*models.Store, error) {
	claims, _ := auth.ClaimsFromContext(ctx)
	query := `
		SELECT id, m_subscription_type_id, coins, expired_date, is_active, name,
		       created_at, created_by, updated_at, updated_by, deleted_at, deleted_by,
		       is_tutorial_completed, tutorial_step
		FROM m_stores
		WHERE id = $1 AND deleted_at IS NULL`
	args := []interface{}{id}

	if claims != nil && !auth.IsSystemAdmin(claims) {
		query += ` AND id = $2`
		args = append(args, claims.StoreID)
	}

	var s models.Store
	err := r.db.QueryRow(ctx, query, args...).Scan(
		&s.ID, &s.SubscriptionTypeID, &s.Coins, &s.ExpiredDate, &s.IsActive, &s.Name,
		&s.CreatedAt, &s.CreatedBy, &s.UpdatedAt, &s.UpdatedBy, &s.DeletedAt, &s.DeletedBy,
		&s.IsTutorialCompleted, &s.TutorialStep,
	)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, nil
		}
		return nil, err
	}
	return &s, nil
}
