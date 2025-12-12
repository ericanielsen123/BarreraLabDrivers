from cappy.config import DATA_PATH
from sweep.sweep_load import pload1d
from time import strftime, localtime
import numpy as np
import matplotlib.pyplot as plt
import os


class Opener:
    def __init__(self, filepath: str, index: int):
        self.idx = index
        self.filepath = filepath

    def getdata(self):
        # Our data is stored in a .tsv.gz file, and this returns a dictionary
        print()
        print(self.filepath, self.idx)
        print()
        data = pload1d(self.filepath, self.idx)
        print(f"Data keys are: {data.keys()}")
        return data

    def plotcfg(self, xlabel="", ylabel="", xscale="linear", yscale="linear"):
        # use 'linear' for linscale, 'log' for logscale
        #'' label for key label, 'Your Label' for your label
        self.xscale = xscale
        self.yscale = yscale
        self.xlabel = xlabel
        self.ylabel = ylabel

    def plot(
        self,
        data: dict,
        keys: list,
        show=True,
        save=False,
    ):
        # Will plot data{key[i]} vs data{key[0]} for all keys.
        # The first key will always be x axis
        for i in range(1, len(keys)):
            plt.plot(data[keys[0]], data[keys[i]], label=keys[i])
            if self.xlabel != "":
                plt.xlabel(self.xlabel)
            elif self.xlabel == "":
                plt.xlabel(keys[0])
            if self.ylabel != "":
                plt.ylabel(self.ylabel)
            elif self.ylabel == "":
                plt.ylabel(keys[i])
            plt.xscale(self.xscale)
            plt.yscale(self.yscale)
            plt.legend()
            if save == True:
                filename = f"{keys[i]}_vs_{keys[0]}.png"
                plotpath = os.path.join(self.filepath, f"{self.idx}", filename)
                plt.savefig(plotpath)
            if show == True:
                plt.show()
            elif show == False:
                plt.clf()


"""
TODO:

Ability to run data from multiple files and plot them on same plot
Ability to store RUN ids on the plot itself.
Store plots in arbitrary locations.
Add labels to describe what is being shown.

"""
