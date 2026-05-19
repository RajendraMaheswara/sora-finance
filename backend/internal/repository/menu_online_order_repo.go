package repository

import (
	"context"
	"errors"
	"sora-finance-api/internal/models"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

type MenuOnlineOrderRepository struct {
	db *pgxpool.Pool
}

func NewMenuOnlineOrderRepository(db *pgxpool.Pool) *MenuOnlineOrderRepository {
	return &MenuOnlineOrderRepository{db: db}
}

func (r *MenuOnlineOrderRepository) GetAll(ctx context.Context) ([]models.MenuOnlineOrder, error) {
	rows, err := r.db.Query(ctx, `
		SELECT id, m_store_id, m_menu_online_order_type_id, m_menu_id, m_menu_packaging_id, is_percentage,
		       name, price, created_at, created_by, updated_at, updated_by, deleted_at, deleted_by
		FROM m_menu_online_orders
		WHERE deleted_at IS NULL
		ORDER BY created_at DESC
	`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var items []models.MenuOnlineOrder
	for rows.Next() {
		var item models.MenuOnlineOrder
		err := rows.Scan(
			&item.ID, &item.StoreID, &item.MenuOnlineOrderTypeID, &item.MenuID, &item.MenuPackagingID,
			&item.IsPercentage, &item.Name, &item.Price, &item.CreatedAt, &item.CreatedBy,
			&item.UpdatedAt, &item.UpdatedBy, &item.DeletedAt, &item.DeletedBy,
		)
		if err != nil {
			return nil, err
		}
		items = append(items, item)
	}
	return items, nil
}

func (r *MenuOnlineOrderRepository) GetByID(ctx context.Context, id uuid.UUID) (*models.MenuOnlineOrder, error) {
	var item models.MenuOnlineOrder
	err := r.db.QueryRow(ctx, `
		SELECT id, m_store_id, m_menu_online_order_type_id, m_menu_id, m_menu_packaging_id, is_percentage,
		       name, price, created_at, created_by, updated_at, updated_by, deleted_at, deleted_by
		FROM m_menu_online_orders
		WHERE id = $1 AND deleted_at IS NULL
	`, id).Scan(
		&item.ID, &item.StoreID, &item.MenuOnlineOrderTypeID, &item.MenuID, &item.MenuPackagingID,
		&item.IsPercentage, &item.Name, &item.Price, &item.CreatedAt, &item.CreatedBy,
		&item.UpdatedAt, &item.UpdatedBy, &item.DeletedAt, &item.DeletedBy,
	)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, nil
		}
		return nil, err
	}
	return &item, nil
}
