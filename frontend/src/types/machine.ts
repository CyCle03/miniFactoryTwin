export type ProductResult = 'GOOD' | 'REJECT'
export type CylinderState = 'retracted' | 'extended'
export type MachineCommand =
  | 'start'
  | 'stop'
  | 'reset'
  | 'emergency_stop'
  | 'emergency_reset'

export interface ProductState {
  id: number
  position: number
  result: ProductResult
}

export interface MachineState {
  timestamp: string
  machine: {
    power: boolean
    running: boolean
    emergency: boolean
  }
  conveyor: {
    running: boolean
    speed: number
  }
  sensors: {
    photo_1: boolean
    photo_2: boolean
  }
  cylinder: {
    state: CylinderState
  }
  production: {
    total: number
    good: number
    reject: number
    ppm: number
  }
  products: ProductState[]
}

export type ConnectionStatus = 'connecting' | 'connected' | 'disconnected'

