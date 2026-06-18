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

type MenuIngredientRepository struct {
	db *pgxpool.Pool
}

func NewMenuIngredientRepository(db *pgxpool.Pool) *MenuIngredientRepository {
	return &MenuIngredientRepository{db: db}
}

func (r *MenuIngredientRepository) GetAll(ctx context.Context) ([]models.MenuIngredient, error) {
	claims, _ := auth.ClaimsFromContext(ctx)
	query := `
		SELECT id, m_store_id, m_menu_id, m_food_ingredient_id, qty,
		       created_at, created_by, updated_at, updated_by, deleted_at, deleted_by
		FROM m_menu_ingredients
		WHERE deleted_at IS NULL`
	var args []interface{}
	if claims != nil && !auth.IsSystemAdmin(claims) {
		query += ` AND m_store_id = $1`
		args = append(args, claims.StoreID)
	}
	query += `
		ORDER BY created_at DESC`
	rows, err := r.db.Query(ctx, query, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var items []models.MenuIngredient
	for rows.Next() {
		var item models.MenuIngredient
		err := rows.Scan(
			&item.ID, &item.StoreID, &item.MenuID, &item.FoodIngredientID, &item.Qty,
			&item.CreatedAt, &item.CreatedBy, &item.UpdatedAt, &item.UpdatedBy, &item.DeletedAt, &item.DeletedBy,
		)
		if err != nil {
			return nil, err
		}
		items = append(items, item)
	}
	return items, nil
}

func (r *MenuIngredientRepository) GetByID(ctx context.Context, id uuid.UUID) (*models.MenuIngredient, error) {
	var item models.MenuIngredient
	claims, _ := auth.ClaimsFromContext(ctx)
	query := `
		SELECT id, m_store_id, m_menu_id, m_food_ingredient_id, qty,
		       created_at, created_by, updated_at, updated_by, deleted_at, deleted_by
		FROM m_menu_ingredients
		WHERE id = $1 AND deleted_at IS NULL
	`
	args := []interface{}{id}
	if claims != nil && !auth.IsSystemAdmin(claims) {
		query += ` AND m_store_id = $2`
		args = append(args, claims.StoreID)
	}
	err := r.db.QueryRow(ctx, query, args...).Scan(
		&item.ID, &item.StoreID, &item.MenuID, &item.FoodIngredientID, &item.Qty,
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
