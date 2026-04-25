package repository

import (
	"context"
	"errors"
	"sora-finance-api/internal/models"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

type IngredientStockHistoryRepository struct {
	db *pgxpool.Pool
}

func NewIngredientStockHistoryRepository(db *pgxpool.Pool) *IngredientStockHistoryRepository {
	return &IngredientStockHistoryRepository{db: db}
}

func (r *IngredientStockHistoryRepository) GetAll(ctx context.Context) ([]models.IngredientStockHistory, error) {
	rows, err := r.db.Query(ctx, `
		SELECT id, m_store_id, m_food_ingredient_id,
		       added, current_stock, date, deleted_note, deleted_reason,
		       journal, note, previous_stock, reduced, remaining_capital,
		       status, stock_change, total_remaining_capital, total_unit_price,
		       type, unit_price,
		       created_at, created_by, updated_at, updated_by, deleted_at, deleted_by
		FROM t_ingredient_stock_histories
		WHERE deleted_at IS NULL
		ORDER BY date DESC NULLS LAST, created_at DESC
	`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var histories []models.IngredientStockHistory
	for rows.Next() {
		var h models.IngredientStockHistory
		err := rows.Scan(
			&h.ID, &h.StoreID, &h.FoodIngredientID,
			&h.Added, &h.CurrentStock, &h.Date, &h.DeletedNote, &h.DeletedReason,
			&h.Journal, &h.Note, &h.PreviousStock, &h.Reduced, &h.RemainingCapital,
			&h.Status, &h.StockChange, &h.TotalRemainingCapital, &h.TotalUnitPrice,
			&h.Type, &h.UnitPrice,
			&h.CreatedAt, &h.CreatedBy, &h.UpdatedAt, &h.UpdatedBy, &h.DeletedAt, &h.DeletedBy,
		)
		if err != nil {
			return nil, err
		}
		histories = append(histories, h)
	}
	return histories, nil
}

func (r *IngredientStockHistoryRepository) GetByID(ctx context.Context, id uuid.UUID) (*models.IngredientStockHistory, error) {
	var h models.IngredientStockHistory
	err := r.db.QueryRow(ctx, `
		SELECT id, m_store_id, m_food_ingredient_id,
		       added, current_stock, date, deleted_note, deleted_reason,
		       journal, note, previous_stock, reduced, remaining_capital,
		       status, stock_change, total_remaining_capital, total_unit_price,
		       type, unit_price,
		       created_at, created_by, updated_at, updated_by, deleted_at, deleted_by
		FROM t_ingredient_stock_histories
		WHERE id = $1 AND deleted_at IS NULL
	`, id).Scan(
		&h.ID, &h.StoreID, &h.FoodIngredientID,
		&h.Added, &h.CurrentStock, &h.Date, &h.DeletedNote, &h.DeletedReason,
		&h.Journal, &h.Note, &h.PreviousStock, &h.Reduced, &h.RemainingCapital,
		&h.Status, &h.StockChange, &h.TotalRemainingCapital, &h.TotalUnitPrice,
		&h.Type, &h.UnitPrice,
		&h.CreatedAt, &h.CreatedBy, &h.UpdatedAt, &h.UpdatedBy, &h.DeletedAt, &h.DeletedBy,
	)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, nil
		}
		return nil, err
	}
	return &h, nil
}