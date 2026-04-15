package repository

import (
	"context"
	"errors"
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

func (r *StoreRepository) GetAll(ctx context.Context) ([]models.Store, error) {
	rows, err := r.db.Query(ctx, `
		SELECT id, m_subscription_type_id, coins, expired_date, is_active, name,
		       created_at, created_by, updated_at, updated_by, deleted_at, deleted_by,
		       is_tutorial_completed, tutorial_step
		FROM m_stores
		WHERE deleted_at IS NULL
		ORDER BY created_at DESC
	`)
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
	return stores, nil
}

func (r *StoreRepository) GetByID(ctx context.Context, id uuid.UUID) (*models.Store, error) {
	var s models.Store
	err := r.db.QueryRow(ctx, `
		SELECT id, m_subscription_type_id, coins, expired_date, is_active, name,
		       created_at, created_by, updated_at, updated_by, deleted_at, deleted_by,
		       is_tutorial_completed, tutorial_step
		FROM m_stores
		WHERE id = $1 AND deleted_at IS NULL
	`, id).Scan(
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

func (r *StoreRepository) Create(ctx context.Context, s *models.Store) error {
	query := `
		INSERT INTO m_stores (
			m_subscription_type_id, coins, expired_date, is_active, name,
			created_by, is_tutorial_completed, tutorial_step
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
		RETURNING id, created_at
	`
	return r.db.QueryRow(ctx, query,
		s.SubscriptionTypeID, s.Coins, s.ExpiredDate, s.IsActive, s.Name,
		s.CreatedBy, s.IsTutorialCompleted, s.TutorialStep,
	).Scan(&s.ID, &s.CreatedAt)
}

func (r *StoreRepository) Update(ctx context.Context, s *models.Store) error {
	query := `
		UPDATE m_stores SET
			m_subscription_type_id = $1,
			coins = $2,
			expired_date = $3,
			is_active = $4,
			name = $5,
			is_tutorial_completed = $6,
			tutorial_step = $7,
			updated_at = NOW(),
			updated_by = $8
		WHERE id = $9 AND deleted_at IS NULL
	`
	cmdTag, err := r.db.Exec(ctx, query,
		s.SubscriptionTypeID, s.Coins, s.ExpiredDate, s.IsActive, s.Name,
		s.IsTutorialCompleted, s.TutorialStep,
		s.UpdatedBy, s.ID,
	)
	if err != nil {
		return err
	}
	if cmdTag.RowsAffected() == 0 {
		return errors.New("store not found or already deleted")
	}
	return nil
}

func (r *StoreRepository) Delete(ctx context.Context, id uuid.UUID, deletedBy uuid.UUID) error {
	query := `
		UPDATE m_stores
		SET deleted_at = NOW(), deleted_by = $1
		WHERE id = $2 AND deleted_at IS NULL
	`
	cmdTag, err := r.db.Exec(ctx, query, deletedBy, id)
	if err != nil {
		return err
	}
	if cmdTag.RowsAffected() == 0 {
		return errors.New("store not found or already deleted")
	}
	return nil
}