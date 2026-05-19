package repository

import (
	"context"
	"errors"
	"sora-finance-api/internal/models"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

type MenuVariantRepository struct {
	db *pgxpool.Pool
}

func NewMenuVariantRepository(db *pgxpool.Pool) *MenuVariantRepository {
	return &MenuVariantRepository{db: db}
}

func (r *MenuVariantRepository) GetAll(ctx context.Context) ([]models.MenuVariant, error) {
	rows, err := r.db.Query(ctx, `
		SELECT id, m_store_id, m_store_regulation_id, cogs, name, price, total_stock,
		       created_at, created_by, updated_at, updated_by, deleted_at, deleted_by
		FROM m_menu_variants
		WHERE deleted_at IS NULL
		ORDER BY created_at DESC
	`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var items []models.MenuVariant
	for rows.Next() {
		var item models.MenuVariant
		err := rows.Scan(
			&item.ID, &item.StoreID, &item.StoreRegulationID, &item.Cogs, &item.Name, &item.Price,
			&item.TotalStock, &item.CreatedAt, &item.CreatedBy, &item.UpdatedAt, &item.UpdatedBy,
			&item.DeletedAt, &item.DeletedBy,
		)
		if err != nil {
			return nil, err
		}
		items = append(items, item)
	}
	return items, nil
}

func (r *MenuVariantRepository) GetByID(ctx context.Context, id uuid.UUID) (*models.MenuVariant, error) {
	var item models.MenuVariant
	err := r.db.QueryRow(ctx, `
		SELECT id, m_store_id, m_store_regulation_id, cogs, name, price, total_stock,
		       created_at, created_by, updated_at, updated_by, deleted_at, deleted_by
		FROM m_menu_variants
		WHERE id = $1 AND deleted_at IS NULL
	`, id).Scan(
		&item.ID, &item.StoreID, &item.StoreRegulationID, &item.Cogs, &item.Name, &item.Price,
		&item.TotalStock, &item.CreatedAt, &item.CreatedBy, &item.UpdatedAt, &item.UpdatedBy,
		&item.DeletedAt, &item.DeletedBy,
	)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, nil
		}
		return nil, err
	}
	return &item, nil
}
