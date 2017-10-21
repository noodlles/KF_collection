from __future__ import print_function
import numpy as np
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from scipy.stats import norm
from sympy import Symbol, symbols, Matrix, sin, cos, sqrt, atan2
from sympy import init_printing
init_printing(use_latex=True)
import numdifftools as nd
import math

dataset = []

# read the measurement data, use 0.0 to stand LIDAR data
# and 1.0 stand RADAR data
with open('data_synthetic.txt', 'rb') as f:
    lines = f.readlines()
    for line in lines:
        line = line.strip('\n')
        line = line.strip()
        numbers = line.split()
        result = []
        for i, item in enumerate(numbers):
            item.strip()
            if i == 0:
                if item == 'L':
                    result.append(0.0)
                else:
                    result.append(1.0)
            else:
                result.append(float(item))
        dataset.append(result)
    f.close()

P = np.diag([1.0, 1.0, 1.0, 1.0, 1.0])
print(P, P.shape)
H_lidar = np.array([[ 1.,  0.,  0.,  0.,  0.],
       [ 0.,  1.,  0.,  0.,  0.]])
print(H_lidar, H_lidar.shape)

R_lidar = np.array([[0.0225, 0.],[0., 0.0225]])
R_radar = np.array([[0.09, 0., 0.],[0., 0.0009, 0.], [0., 0., 0.09]])
print(R_lidar, R_lidar.shape)
print(R_radar, R_radar.shape)

# process noise standard deviation for a
std_noise_a = 2.0
# process noise standard deviation for yaw acceleration
std_noise_yaw_dd = 0.3


def control_psi(psi):
    while (psi > np.pi or psi < -np.pi):
        if psi > np.pi:
            psi = psi - 2 * np.pi
        if psi < -np.pi:
            psi = psi + 2 * np.pi
    return psi

state = np.zeros(5)
init_measurement = dataset[0]
current_time = 0.0
if init_measurement[0] == 0.0:
    print('Initialize with LIDAR measurement!')
    current_time = init_measurement[3]
    state[0] = init_measurement[1]
    state[1] = init_measurement[2]

else:
    print('Initialize with RADAR measurement!')
    current_time = init_measurement[4]
    init_rho = init_measurement[1]
    init_psi = init_measurement[2]
    init_psi = control_psi(init_psi)
    state[0] = init_rho * np.cos(init_psi)
    state[1] = init_rho * np.sin(init_psi)
print(state, state.shape)

# Preallocation for Plotting
px = []
py = []
vx = []
vy = []

gpx = []
gpy = []
gvx = []
gvy = []

mx = []
my = []


def savestates(ss, gx, gy, gv1, gv2, m1, m2):
    px.append(ss[0])
    py.append(ss[1])
    vx.append(np.cos(ss[3]) * ss[2])
    vy.append(np.sin(ss[3]) * ss[2])

    gpx.append(gx)
    gpy.append(gy)
    gvx.append(gv1)
    gvy.append(gv2)
    mx.append(m1)
    my.append(m2)


measurement_step = len(dataset)
state = state.reshape([5, 1])
dt = 0.05

I = np.eye(5)

transition_function = lambda y: np.vstack((
    y[0] + (y[2] / y[4]) * (np.sin(y[3] + y[4] * dt) - np.sin(y[3])),
    y[1] + (y[2] / y[4]) * (-np.cos(y[3] + y[4] * dt) + np.cos(y[3])),
    y[2],
    y[3] + y[4] * dt,
    y[4]))

# when omega is 0
transition_function_1 = lambda m: np.vstack((m[0] + m[2] * np.cos(m[3]) * dt,
                                             m[1] + m[2] * np.sin(m[3]) * dt,
                                             m[2],
                                             m[3] + m[4] * dt,
                                             m[4]))

J_A = nd.Jacobian(transition_function)
J_A_1 = nd.Jacobian(transition_function_1)
# print(J_A([1., 2., 3., 4., 5.]))

measurement_function = lambda k: np.vstack((np.sqrt(k[0] * k[0] + k[1] * k[1]),
                                            math.atan2(k[1], k[0]),
                                            (k[0] * k[2] * np.cos(k[3]) + k[1] * k[2] * np.sin(k[3])) / np.sqrt(k[0] * k[0] + k[1] * k[1])))
J_H = nd.Jacobian(measurement_function)
# J_H([1., 2., 3., 4., 5.])

for step in range(1, measurement_step):

    # Prediction
    # ========================
    t_measurement = dataset[step]
    if t_measurement[0] == 0.0:
        m_x = t_measurement[1]
        m_y = t_measurement[2]
        z = np.array([[m_x], [m_y]])

        dt = (t_measurement[3] - current_time) / 1000000.0
        current_time = t_measurement[3]

        # true position
        g_x = t_measurement[4]
        g_y = t_measurement[5]
        g_v_x = t_measurement[6]
        g_v_y = t_measurement[7]

    else:
        m_rho = t_measurement[1]
        m_psi = t_measurement[2]
        m_dot_rho = t_measurement[3]
        z = np.array([[m_rho], [m_psi], [m_dot_rho]])

        dt = (t_measurement[4] - current_time) / 1000000.0
        current_time = t_measurement[4]

        # true position
        g_x = t_measurement[5]
        g_y = t_measurement[6]
        g_v_x = t_measurement[7]
        g_v_y = t_measurement[8]

    # Q = np.diag([(0.5*(dt**2)*math.cos(state.ravel().tolist()[3])*std_noise_a)**2,
    #              (0.5*dt**2*math.sin(state.ravel().tolist()[3])*std_noise_a)**2,
    #              (dt*std_noise_a)**2,
    #              (0.5*dt**2*std_noise_yaw_dd)**2,
    #              (dt*std_noise_yaw_dd)])

    #     print(Q)

    if np.abs(state[4, 0]) < 0.0001:  # omega is 0, Driving straight
        state = transition_function_1(state.ravel().tolist())
        state[3, 0] = control_psi(state[3, 0])
        JA = J_A_1(state.ravel().tolist())
    else:  # otherwise
        state = transition_function(state.ravel().tolist())
        state[3, 0] = control_psi(state[3, 0])
        JA = J_A(state.ravel().tolist())


    G = np.zeros([5, 2])
    G[0, 0] = 0.5 * dt * dt * np.cos(state[3, 0])
    G[1, 0] = 0.5 * dt * dt * np.sin(state[3, 0])
    G[2, 0] = dt
    G[3, 1] = 0.5 * dt * dt
    G[4, 1] = dt

    Q_v = np.diag([std_noise_a*std_noise_a, std_noise_yaw_dd*std_noise_yaw_dd])
    Q = np.dot(np.dot(G, Q_v), G.T)

    # Project the error covariance ahead
    P = np.dot(np.dot(JA, P), JA.T) + Q

    # Measurement Update (Correction)
    # ===============================
    if t_measurement[0] == 0.0:
        # Lidar
        S = np.dot(np.dot(H_lidar, P), H_lidar.T) + R_lidar
        K = np.dot(np.dot(P, H_lidar.T), np.linalg.inv(S))

        y = z - np.dot(H_lidar, state)
        y[1, 0] = control_psi(y[1, 0])
        state = state + np.dot(K, y)
        state[3, 0] = control_psi(state[3, 0])
        # Update the error covariance
        P = np.dot((I - np.dot(K, H_lidar)), P)

        # Save states for Plotting
        savestates(state.ravel().tolist(), g_x, g_y, g_v_x, g_v_y, m_x, m_y)

    else:
        # Radar
        JH = J_H(state.ravel().tolist())

        S = np.dot(np.dot(JH, P), JH.T) + R_radar
        K = np.dot(np.dot(P, JH.T), np.linalg.inv(S))
        map_pred = measurement_function(state.ravel().tolist())
        if np.abs(map_pred[0, 0]) < 0.0001:
            # if rho is 0
            map_pred[2, 0] = 0

        y = z - map_pred
        y[1, 0] = control_psi(y[1, 0])

        state = state + np.dot(K, y)
        state[3, 0] = control_psi(state[3, 0])
        # Update the error covariance
        P = np.dot((I - np.dot(K, JH)), P)

        savestates(state.ravel().tolist(), g_x, g_y, g_v_x, g_v_y, m_rho * np.cos(m_psi), m_rho * np.sin(m_psi))

def rmse(estimates, actual):
    result = np.sqrt(np.mean((estimates-actual)**2))
    return result

print(rmse(np.array(px), np.array(gpx)),
      rmse(np.array(py), np.array(gpy)),
      rmse(np.array(vx), np.array(gvx)),
      rmse(np.array(vy), np.array(gvy)))

# write to the output file
stack = [px, py, vx, vy, mx, my, gpx, gpy, gvx, gvy]
stack = np.array(stack)
stack = stack.T
np.savetxt('output.csv', stack, '%.6f')
