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

type FoodIngredientRepository struct {
	db *pgxpool.Pool
}

func NewFoodIngredientRepository(db *pgxpool.Pool) *FoodIngredientRepository {
	return &FoodIngredientRepository{db: db}
}

func (r *FoodIngredientRepository) GetAll(ctx context.Context) ([]models.FoodIngredient, error) {
	claims, _ := auth.ClaimsFromContext(ctx)
	query := `
		SELECT id, m_store_id, m_food_unit_id, code, deleted_note, deleted_reason, name, note,
		       stock_limit, unit_price, created_at, created_by, updated_at, updated_by, deleted_at, deleted_by
		FROM m_food_ingredients
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

	var items []models.FoodIngredient
	for rows.Next() {
		var item models.FoodIngredient
		err := rows.Scan(
			&item.ID, &item.StoreID, &item.FoodUnitID, &item.Code, &item.DeletedNote, &item.DeletedReason,
			&item.Name, &item.Note, &item.StockLimit, &item.UnitPrice, &item.CreatedAt, &item.CreatedBy,
			&item.UpdatedAt, &item.UpdatedBy, &item.DeletedAt, &item.DeletedBy,
		)
		if err != nil {
			return nil, err
		}
		items = append(items, item)
	}
	return items, nil
}

func (r *FoodIngredientRepository) GetByID(ctx context.Context, id uuid.UUID) (*models.FoodIngredient, error) {
	var item models.FoodIngredient
	claims, _ := auth.ClaimsFromContext(ctx)
	query := `
		SELECT id, m_store_id, m_food_unit_id, code, deleted_note, deleted_reason, name, note,
		       stock_limit, unit_price, created_at, created_by, updated_at, updated_by, deleted_at, deleted_by
		FROM m_food_ingredients
		WHERE id = $1 AND deleted_at IS NULL
	`
	args := []interface{}{id}
	if claims != nil && !auth.IsSystemAdmin(claims) {
		query += ` AND m_store_id = $2`
		args = append(args, claims.StoreID)
	}
	err := r.db.QueryRow(ctx, query, args...).Scan(
		&item.ID, &item.StoreID, &item.FoodUnitID, &item.Code, &item.DeletedNote, &item.DeletedReason,
		&item.Name, &item.Note, &item.StockLimit, &item.UnitPrice, &item.CreatedAt, &item.CreatedBy,
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
