package repository

import (
	"context"
	"errors"
	"sora-finance-api/internal/models"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

type SubscriptionTypeRepository struct {
	db *pgxpool.Pool
}

func NewSubscriptionTypeRepository(db *pgxpool.Pool) *SubscriptionTypeRepository {
	return &SubscriptionTypeRepository{db: db}
}

func (r *SubscriptionTypeRepository) GetAll(ctx context.Context) ([]models.SubscriptionType, error) {
	rows, err := r.db.Query(ctx, `
		SELECT id, coins, day, description, image_url, is_active, max_users, name,
		       created_at, created_by, updated_at, updated_by, deleted_at, deleted_by
		FROM m_subscription_types
		WHERE deleted_at IS NULL
		ORDER BY created_at DESC
	`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var items []models.SubscriptionType
	for rows.Next() {
		var item models.SubscriptionType
		err := rows.Scan(
			&item.ID, &item.Coins, &item.Day, &item.Description, &item.ImageURL, &item.IsActive,
			&item.MaxUsers, &item.Name, &item.CreatedAt, &item.CreatedBy, &item.UpdatedAt,
			&item.UpdatedBy, &item.DeletedAt, &item.DeletedBy,
		)
		if err != nil {
			return nil, err
		}
		items = append(items, item)
	}
	return items, nil
}

func (r *SubscriptionTypeRepository) GetByID(ctx context.Context, id int64) (*models.SubscriptionType, error) {
	var item models.SubscriptionType
	err := r.db.QueryRow(ctx, `
		SELECT id, coins, day, description, image_url, is_active, max_users, name,
		       created_at, created_by, updated_at, updated_by, deleted_at, deleted_by
		FROM m_subscription_types
		WHERE id = $1 AND deleted_at IS NULL
	`, id).Scan(
		&item.ID, &item.Coins, &item.Day, &item.Description, &item.ImageURL, &item.IsActive,
		&item.MaxUsers, &item.Name, &item.CreatedAt, &item.CreatedBy, &item.UpdatedAt,
		&item.UpdatedBy, &item.DeletedAt, &item.DeletedBy,
	)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, nil
		}
		return nil, err
	}
	return &item, nil
}
