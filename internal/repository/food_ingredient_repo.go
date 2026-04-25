package repository

import (
	"context"
	"errors"
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
	rows, err := r.db.Query(ctx, `
		SELECT id, m_store_id, m_food_unit_id, code, deleted_note, deleted_reason,
		       name, note, stock_limit, unit_price,
		       created_at, created_by, updated_at, updated_by, deleted_at, deleted_by
		FROM m_food_ingredients
		WHERE deleted_at IS NULL
		ORDER BY name ASC
	`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var ingredients []models.FoodIngredient
	for rows.Next() {
		var i models.FoodIngredient
		err := rows.Scan(
			&i.ID, &i.StoreID, &i.FoodUnitID, &i.Code, &i.DeletedNote, &i.DeletedReason,
			&i.Name, &i.Note, &i.StockLimit, &i.UnitPrice,
			&i.CreatedAt, &i.CreatedBy, &i.UpdatedAt, &i.UpdatedBy, &i.DeletedAt, &i.DeletedBy,
		)
		if err != nil {
			return nil, err
		}
		ingredients = append(ingredients, i)
	}
	return ingredients, nil
}

func (r *FoodIngredientRepository) GetByID(ctx context.Context, id uuid.UUID) (*models.FoodIngredient, error) {
	var i models.FoodIngredient
	err := r.db.QueryRow(ctx, `
		SELECT id, m_store_id, m_food_unit_id, code, deleted_note, deleted_reason,
		       name, note, stock_limit, unit_price,
		       created_at, created_by, updated_at, updated_by, deleted_at, deleted_by
		FROM m_food_ingredients
		WHERE id = $1 AND deleted_at IS NULL
	`, id).Scan(
		&i.ID, &i.StoreID, &i.FoodUnitID, &i.Code, &i.DeletedNote, &i.DeletedReason,
		&i.Name, &i.Note, &i.StockLimit, &i.UnitPrice,
		&i.CreatedAt, &i.CreatedBy, &i.UpdatedAt, &i.UpdatedBy, &i.DeletedAt, &i.DeletedBy,
	)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, nil
		}
		return nil, err
	}
	return &i, nil
}
