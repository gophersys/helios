# Test Cluster Python Library

This library is the python implementation of the concept of test clusters. Since we have to create a new cluster for every product we make, some abstractions are made here that facilitate the creation and serving of these cluster across the network.

# Architecture

A cluster consists of multiple MTIB boards. All of these are connected into a single kubernetes cluster. Additional to the MTIB boards, there's also a separate Linux host, which isnt' part of the cluster, and acts as an controller for the cluster. 

The job of the controller is to abstract away the complexity of synchronicity and concurrency into a single end point (server).

# Controller

The controller refers to a set of software features that allow a single application to act as the main interface and controller of a kubernets cluster. The use of this application is to guarantee service availability, implement self healing capabilites as well as an easy way to update, monitor and collect logs from the cluster.

# Cluster Registration

