package models

type ForecastSaveInput struct {
	Run     ForecastRunInput      `json:"run"`
	Results []ForecastResultInput `json:"results"`
}
