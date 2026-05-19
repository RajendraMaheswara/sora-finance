package repository

import (
	"context"
	"errors"
	"sora-finance-api/internal/models"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

type MenuPackagingIngredientRepository struct {
	db *pgxpool.Pool
}

func NewMenuPackagingIngredientRepository(db *pgxpool.Pool) *MenuPackagingIngredientRepository {
	return &MenuPackagingIngredientRepository{db: db}
}

func (r *MenuPackagingIngredientRepository) GetAll(ctx context.Context) ([]models.MenuPackagingIngredient, error) {
	rows, err := r.db.Query(ctx, `
		SELECT id, m_store_id, m_menu_packaging_id, m_food_ingredient_id, qty,
		       created_at, created_by, updated_at, updated_by, deleted_at, deleted_by
		FROM m_menu_packaging_ingredients
		WHERE deleted_at IS NULL
		ORDER BY created_at DESC
	`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var items []models.MenuPackagingIngredient
	for rows.Next() {
		var item models.MenuPackagingIngredient
		err := rows.Scan(
			&item.ID, &item.StoreID, &item.MenuPackagingID, &item.FoodIngredientID, &item.Qty,
			&item.CreatedAt, &item.CreatedBy, &item.UpdatedAt, &item.UpdatedBy, &item.DeletedAt, &item.DeletedBy,
		)
		if err != nil {
			return nil, err
		}
		items = append(items, item)
	}
	return items, nil
}

func (r *MenuPackagingIngredientRepository) GetByID(ctx context.Context, id uuid.UUID) (*models.MenuPackagingIngredient, error) {
	var item models.MenuPackagingIngredient
	err := r.db.QueryRow(ctx, `
		SELECT id, m_store_id, m_menu_packaging_id, m_food_ingredient_id, qty,
		       created_at, created_by, updated_at, updated_by, deleted_at, deleted_by
		FROM m_menu_packaging_ingredients
		WHERE id = $1 AND deleted_at IS NULL
	`, id).Scan(
		&item.ID, &item.StoreID, &item.MenuPackagingID, &item.FoodIngredientID, &item.Qty,
		&item.CreatedAt, &item.CreatedBy, &item.UpdatedAt, &item.UpdatedBy, &item.DeletedAt, &item.DeletedBy,
	)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, nil
		}
		return nil, err
	}
	return &item, nil
}
