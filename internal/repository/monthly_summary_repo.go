package repository

import (
	"context"
	"errors"
	"sora-finance-api/internal/models"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

type MonthlySummaryRepository struct {
	db *pgxpool.Pool
}

func NewMonthlySummaryRepository(db *pgxpool.Pool) *MonthlySummaryRepository {
	return &MonthlySummaryRepository{db: db}
}

func (r *MonthlySummaryRepository) GetAll(ctx context.Context) ([]models.MonthlySummary, error) {
	rows, err := r.db.Query(ctx, `
		SELECT id, m_store_id, date, total_cash, total_rounding, total_debit, total_ewallet,
		       total_income, total_regulation_outlet, total_regulation_customer, total_hpp,
		       total_discount, total_cost_and_expense, total_net_income,
		       created_at, created_by, updated_at, updated_by, deleted_at, deleted_by
		FROM t_finance_monthly_summaries
		WHERE deleted_at IS NULL
		ORDER BY date DESC
	`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var summaries []models.MonthlySummary
	for rows.Next() {
		var s models.MonthlySummary
		err := rows.Scan(
			&s.ID, &s.StoreID, &s.Date,
			&s.TotalCash, &s.TotalRounding, &s.TotalDebit, &s.TotalEwallet,
			&s.TotalIncome, &s.TotalRegulationOutlet, &s.TotalRegulationCustomer,
			&s.TotalHPP, &s.TotalDiscount, &s.TotalCostAndExpense, &s.TotalNetIncome,
			&s.CreatedAt, &s.CreatedBy, &s.UpdatedAt, &s.UpdatedBy, &s.DeletedAt, &s.DeletedBy,
		)
		if err != nil {
			return nil, err
		}
		summaries = append(summaries, s)
	}
	return summaries, nil
}

func (r *MonthlySummaryRepository) GetByID(ctx context.Context, id uuid.UUID) (*models.MonthlySummary, error) {
	var s models.MonthlySummary
	err := r.db.QueryRow(ctx, `
		SELECT id, m_store_id, date, total_cash, total_rounding, total_debit, total_ewallet,
		       total_income, total_regulation_outlet, total_regulation_customer, total_hpp,
		       total_discount, total_cost_and_expense, total_net_income,
		       created_at, created_by, updated_at, updated_by, deleted_at, deleted_by
		FROM t_finance_monthly_summaries
		WHERE id = $1 AND deleted_at IS NULL
	`, id).Scan(
		&s.ID, &s.StoreID, &s.Date,
		&s.TotalCash, &s.TotalRounding, &s.TotalDebit, &s.TotalEwallet,
		&s.TotalIncome, &s.TotalRegulationOutlet, &s.TotalRegulationCustomer,
		&s.TotalHPP, &s.TotalDiscount, &s.TotalCostAndExpense, &s.TotalNetIncome,
		&s.CreatedAt, &s.CreatedBy, &s.UpdatedAt, &s.UpdatedBy, &s.DeletedAt, &s.DeletedBy,
	)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, nil
		}
		return nil, err
	}
	return &s, nil
}