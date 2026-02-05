import { useFetchData } from './use-fetch-data';
import { ChipsetConfig } from '../types/models';

export function useChipsetConfig() {
  return useFetchData<ChipsetConfig>('/v2/products/chipsets');
}
